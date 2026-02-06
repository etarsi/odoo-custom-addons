#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import base64
import hashlib
import argparse
from pathlib import Path
from collections import defaultdict, deque
import xmlrpc.client

# Opcional: solo si usás --sync-links
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
except Exception:
    service_account = None
    build = None

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Soporta:
# 52358 - 55781
# 52358_...
# [52358] ...
# 52358 ...
LEADING_CODE_RE = re.compile(r"^\s*[\[\(\{]*\s*([0-9A-Za-z]+)")


def extract_leading_code(name: str):
    if not name:
        return None
    m = LEADING_CODE_RE.match(name.strip())
    return m.group(1) if m else None


def is_image(path: Path):
    return path.suffix.lower() in IMAGE_EXTS


def load_state(state_file):
    if not os.path.exists(state_file):
        return {}
    with open(state_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state_file, data):
    tmp = state_file + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, state_file)


def signature_for_files(paths, root):
    """
    Firma rápida por ruta relativa + size + mtime_ns
    (evita leer bytes completos de todas las imágenes)
    """
    h = hashlib.sha1()
    for p in sorted(paths):
        st = p.stat()
        rel = str(p.relative_to(root)).replace("\\", "/")
        h.update(rel.encode("utf-8"))
        h.update(str(st.st_size).encode("utf-8"))
        h.update(str(st.st_mtime_ns).encode("utf-8"))
    return h.hexdigest()


def find_code_from_path(dir_path: Path, root: Path):
    """
    Busca código en el nombre de carpeta más cercano (desde hoja hacia arriba)
    """
    rel_parts = dir_path.relative_to(root).parts
    for part in reversed(rel_parts):
        code = extract_leading_code(part)
        if code:
            return code
    return None


def build_local_code_images_map(root: Path, exclude_prefixes=None):
    """
    Mapea: code -> [lista de imágenes]
    """
    code_map = defaultdict(list)
    exclude_prefixes = exclude_prefixes or []

    for dirpath, _, filenames in os.walk(root):
        d = Path(dirpath)
        code = find_code_from_path(d, root)
        if not code:
            continue
        if any(code.startswith(pref) for pref in exclude_prefixes):
            continue

        for fn in filenames:
            p = d / fn
            if is_image(p):
                code_map[code].append(p)

    # orden estable
    for k in list(code_map.keys()):
        code_map[k] = sorted(code_map[k], key=lambda x: str(x).lower())

    return code_map


class OdooRPC:
    def __init__(self, url, db, username, password):
        self.url = url.rstrip("/")
        self.db = db
        self.username = username
        self.password = password

        self.common = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/common", allow_none=True)
        self.models = xmlrpc.client.ServerProxy(f"{self.url}/xmlrpc/2/object", allow_none=True)

        uid = self.common.authenticate(self.db, self.username, self.password, {})
        if not uid:
            raise RuntimeError("No se pudo autenticar en Odoo.")
        self.uid = uid

    def execute(self, model, method, *args, **kwargs):
        return self.models.execute_kw(
            self.db, self.uid, self.password, model, method, args, kwargs or {}
        )

    def search(self, model, domain, limit=None):
        kw = {}
        if limit:
            kw["limit"] = limit
        return self.execute(model, "search", domain, **kw)

    def read(self, model, ids, fields):
        if not ids:
            return []
        return self.execute(model, "read", ids, {"fields": fields})

    def write(self, model, ids, vals):
        return self.execute(model, "write", ids, vals)

    def create(self, model, vals):
        return self.execute(model, "create", vals)

    def unlink(self, model, ids):
        if ids:
            return self.execute(model, "unlink", ids)
        return True


def b64_from_file(path: Path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def update_product_images(odoo: OdooRPC, tmpl_id: int, image_paths):
    """
    Reemplaza foto principal + galería de product.image
    """
    if not image_paths:
        return False

    # Foto principal: primera imagen ordenada
    main_b64 = b64_from_file(image_paths[0])
    odoo.write("product.template", [tmpl_id], {"image_1920": main_b64})

    # Limpiar galería actual
    old_imgs = odoo.search("product.image", [("product_tmpl_id", "=", tmpl_id)])
    if old_imgs:
        odoo.unlink("product.image", old_imgs)

    # Crear galería
    for p in image_paths:
        odoo.create("product.image", {
            "product_tmpl_id": tmpl_id,
            "name": p.name,
            "image_1920": b64_from_file(p),
        })

    return True


# ---------- Sync links (opcional) ----------

def build_drive_service(service_account_json):
    if service_account is None or build is None:
        raise RuntimeError("Faltan dependencias google-api-python-client/google-auth")
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = service_account.Credentials.from_service_account_file(service_account_json, scopes=scopes)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def drive_list_subfolders(service, parent_id):
    out = []
    page_token = None
    q = f"'{parent_id}' in parents and trashed=false and mimeType='application/vnd.google-apps.folder'"
    while True:
        resp = service.files().list(
            q=q,
            fields="nextPageToken, files(id,name,parents)",
            pageSize=1000,
            pageToken=page_token,
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
        ).execute()
        out.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return out


def build_code_folder_map(service, main_folder_id, max_depth=None):
    """
    Recorre carpetas bajo main_folder_id y arma:
    code -> best folder_id
    """
    best = {}  # code -> (score_tuple, folder_id, folder_name)

    q = deque([(main_folder_id, 0)])
    visited = set()

    while q:
        parent_id, depth = q.popleft()
        if parent_id in visited:
            continue
        visited.add(parent_id)

        if max_depth is not None and depth >= max_depth:
            continue

        subs = drive_list_subfolders(service, parent_id)
        for f in subs:
            fid = f["id"]
            name = (f.get("name") or "").strip()
            code = extract_leading_code(name)
            if code:
                code_l = code.lower()
                # score: exacto == 3, prefijo == 2; menos profundidad; nombre corto
                rank = 3 if name.lower() == code_l else 2
                sc = (rank, -depth, -len(name))
                prev = best.get(code_l)
                if (prev is None) or (sc > prev[0]):
                    best[code_l] = (sc, fid, name)
            q.append((fid, depth + 1))

    return {k: {"id": v[1], "name": v[2]} for k, v in best.items()}


def main():
    ap = argparse.ArgumentParser(description="Sync imágenes locales a Odoo (y opcional links gdrive_folder_id)")
    ap.add_argument("--odoo-url", required=True)
    ap.add_argument("--odoo-db", required=True)
    ap.add_argument("--odoo-user", required=True)
    ap.add_argument("--odoo-pass", required=True)

    ap.add_argument("--image-root", required=True, help="Ej: /opt/odoo15/image/SEBIGUS 2024")
    ap.add_argument("--state-file", default="/opt/odoo15/image/.sync_state.json")
    ap.add_argument("--limit", type=int, default=0, help="0 = sin límite")
    ap.add_argument("--exclude-prefix", action="append", default=[], help="Ej: --exclude-prefix 9")
    ap.add_argument("--dry-run", action="store_true")

    # opcional links
    ap.add_argument("--sync-links", action="store_true", help="Actualizar gdrive_folder_id por default_code")
    ap.add_argument("--service-account-json", default="")
    ap.add_argument("--drive-main-folder-id", default="")
    ap.add_argument("--drive-max-depth", type=int, default=0, help="0 = ilimitado")

    args = ap.parse_args()

    root = Path(args.image_root).resolve()
    if not root.exists():
        raise RuntimeError(f"No existe image-root: {root}")

    odoo = OdooRPC(args.odoo_url, args.odoo_db, args.odoo_user, args.odoo_pass)

    # 1) Map local code -> imágenes
    code_images = build_local_code_images_map(root, exclude_prefixes=args.exclude_prefix)
    if args.limit > 0:
        # recorta por cantidad de códigos
        keys = list(code_images.keys())[:args.limit]
        code_images = {k: code_images[k] for k in keys}

    # 2) (opcional) map code -> folder_id Drive
    code_drive = {}
    if args.sync_links:
        if not args.service_account_json or not args.drive_main_folder_id:
            raise RuntimeError("--sync-links requiere --service-account-json y --drive-main-folder-id")
        service = build_drive_service(args.service_account_json)
        depth = None if args.drive_max_depth == 0 else args.drive_max_depth
        code_drive = build_code_folder_map(service, args.drive_main_folder_id, max_depth=depth)

    # 3) Estado incremental
    state = load_state(args.state_file)

    updated_links = 0
    updated_imgs = 0
    unchanged = 0
    missing_product = 0
    errors = 0

    for code, imgs in code_images.items():
        code_l = code.lower()

        tmpl_ids = odoo.search("product.template", [("default_code", "=", code)], limit=1)
        if not tmpl_ids:
            missing_product += 1
            continue
        tmpl_id = tmpl_ids[0]

        sig = signature_for_files(imgs, root)
        st_key = str(tmpl_id)
        prev_sig = state.get(st_key, {}).get("sig")
        prev_folder = state.get(st_key, {}).get("folder_id", "")

        # link target opcional
        new_folder_id = ""
        if args.sync_links and code_l in code_drive:
            new_folder_id = code_drive[code_l]["id"]

        link_changed = bool(new_folder_id and new_folder_id != prev_folder)
        img_changed = (sig != prev_sig)

        if not link_changed and not img_changed:
            unchanged += 1
            continue

        try:
            if args.dry_run:
                continue

            # update link
            if new_folder_id:
                odoo.write("product.template", [tmpl_id], {"gdrive_folder_id": new_folder_id})
                updated_links += 1

            # update images
            if img_changed:
                ok = update_product_images(odoo, tmpl_id, imgs)
                if ok:
                    updated_imgs += 1

            state[st_key] = {
                "code": code,
                "sig": sig,
                "folder_id": new_folder_id or prev_folder or "",
            }

        except Exception as e:
            errors += 1
            print(f"[ERROR] code={code} tmpl_id={tmpl_id}: {e}")

    if not args.dry_run:
        save_state(args.state_file, state)

    print("=== RESUMEN ===")
    print(f"Productos con imágenes detectadas: {len(code_images)}")
    print(f"Links actualizados: {updated_links}")
    print(f"Imágenes actualizadas: {updated_imgs}")
    print(f"Sin cambios: {unchanged}")
    print(f"Sin producto en Odoo: {missing_product}")
    print(f"Errores: {errors}")


if __name__ == "__main__":
    main()
