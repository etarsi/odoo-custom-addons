# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

import base64
import io
import os
import re
import time
import logging
import tempfile
import urllib.parse
import socket
import ipaddress
import subprocess
import shutil

from datetime import date
from calendar import monthrange
from psycopg2.extras import execute_values

_logger = logging.getLogger(__name__)

try:
    import requests
except Exception:
    requests = None


COMPANY_IDS = [2, 3, 4]


class ImportAfipIibbWizard(models.TransientModel):
    _name = 'import.afip.iibb.wizard'
    _description = 'Wizard: Importar AFIP (Impuestos Brutos)'

    # ----------------- ORIGEN -----------------
    url = fields.Char('URL de descarga (servidor)')
    month = fields.Selection(
        selection=[(str(i), date(1900, i, 1).strftime('%B')) for i in range(1, 13)],
        string='Mes',
        required=True,
        default=lambda self: str(fields.Date.today().month),
    )
    year = fields.Integer(
        string='Año',
        required=True,
        default=lambda self: fields.Date.today().year,
    )
    delimiter = fields.Char(string='Separador', default=';')
    cuit_index = fields.Integer(string='Indice CUIT', default=3)
    percepcion_index = fields.Integer(string='Indice Percepcion', default=7)
    retencion_index = fields.Integer(string='Indice Retencion', default=8)
    tag_id = fields.Integer(string='ID de Tag', default=19)
    max_download_mb = fields.Integer(string='Máx MB descarga', default=350)
    _re_digits = re.compile(r"\D+")

    # ----------------- HELPERS NUMERICOS -----------------
    def _norm_cuit(self, v):
        if not v:
            return False
        return self._re_digits.sub("", str(v)) or False

    def _to_float(self, v):
        if v in (None, '', False):
            return 0.0
        try:
            s = str(v).strip()
            # "1.234,56" -> "1234.56"
            if s.count(',') == 1:
                s = s.replace('.', '').replace(',', '.')
            else:
                s = s.replace(',', '.')
            return float(s)
        except Exception:
            return 0.0
        
    def _is_rar_file(self, path):
        try:
            with open(path, "rb") as f:
                sig = f.read(8)
            return sig.startswith(b"Rar!\x1a\x07")  # rar4/rar5
        except Exception:
            return False

    # ----------------- DOWNLOAD (URL -> DISCO) -----------------
    def _pick_extracted_text_file(self, extract_dir):
        candidates = []
        for root, dirnames, filenames in os.walk(extract_dir):
            for fn in filenames:
                fp = os.path.join(root, fn)
                ext = os.path.splitext(fn)[1].lower()
                if ext in (".txt", ".csv", ".dat"):
                    try:
                        candidates.append((os.path.getsize(fp), fp))
                    except Exception:
                        pass
        if not candidates:
            raise UserError(_("RAR extraído, pero no se encontró TXT/CSV/DAT dentro."))
        candidates.sort(reverse=True)
        return candidates[0][1]

    def _extract_if_needed(self, downloaded_path, target_dir):
        downloaded_path = os.path.realpath(downloaded_path)
        ext = os.path.splitext(downloaded_path)[1].lower()
        if ext != ".rar" and not self._is_rar_file(downloaded_path):
            return downloaded_path

        unrar = shutil.which("unrar")
        sevenz = shutil.which("7z") or shutil.which("7zz")

        if not unrar and not sevenz:
            raise UserError(_("No se encontró extractor RAR. Instalá: sudo apt-get install unrar"))

        base = os.path.splitext(os.path.basename(downloaded_path))[0]
        extract_dir = os.path.realpath(os.path.join(os.path.realpath(target_dir), f"{base}_extracted"))
        os.makedirs(extract_dir, exist_ok=True)

        def run(cmd):
            return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

        out_unrar = ""
        if unrar:
            cmd = [unrar, "x", "-o+", downloaded_path, extract_dir + os.sep]
            p = run(cmd)
            out_unrar = p.stdout or ""
            if p.returncode == 0:
                return self._pick_extracted_text_file(extract_dir)

        if sevenz:
            cmd = [sevenz, "x", "-y", f"-o{extract_dir}", downloaded_path]
            p = run(cmd)
            out_7z = p.stdout or ""
            if p.returncode == 0:
                return self._pick_extracted_text_file(extract_dir)

            raise UserError(_("Error extrayendo RAR.\n\nUNRAR:\n%s\n\n7Z:\n%s") % (out_unrar[-1200:], out_7z[-1200:]))

        raise UserError(_("Error extrayendo RAR con unrar:\n%s") % (out_unrar[-2000:]))

    def _get_download_dir(self):
        """
        Directorio destino para guardar el TXT descargado.
        - Si existe el parámetro afip_iibb.download_dir lo usa.
        - Si no, usa /opt/odoo/afip_iibb
        """
        base_dir = '/opt/odoo/afip_iibb'

        if not base_dir:
            raise UserError(_("No está configurada la ruta de descarga (afip_iibb.download_dir)."))

        base_dir = os.path.realpath(base_dir)

        # Intentar crear si no existe (si el usuario del servicio tiene permisos)
        if not os.path.isdir(base_dir):
            try:
                os.makedirs(base_dir, exist_ok=True)
            except Exception:
                raise UserError(_("La carpeta no existe y no se pudo crear: %s") % base_dir)

        # Test write
        if not os.access(base_dir, os.W_OK):
            raise UserError(_("Odoo no tiene permisos de escritura en: %s") % base_dir)

        return base_dir

    def _sanitize_filename(self, name):
        name = (name or "").strip()
        name = os.path.basename(name)  # evita rutas
        name = re.sub(r"[^a-zA-Z0-9._-]+", "_", name)
        return name or "padron_afip_iibb.txt"

    def _validate_url(self, url):
        """Mitigación SSRF básica + whitelist opcional por dominios."""
        p = urllib.parse.urlparse(url or "")
        if p.scheme not in ("http", "https"):
            raise UserError(_("Solo se permite http/https."))
        if not p.hostname:
            raise UserError(_("URL inválida (sin host)."))

        host = p.hostname.strip().lower()

        # Bloqueo SSRF simple: loopback/privadas/link-local
        try:
            ip = socket.gethostbyname(host)
            ip_obj = ipaddress.ip_address(ip)
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
                raise UserError(_("Host no permitido (privado/loopback)."))
        except UserError:
            raise
        except Exception:
            raise UserError(_("No se pudo resolver el host."))

        # Whitelist opcional por parámetro:
        # afip_iibb.allowed_domains = drive.google.com,tu-dominio.com
        allowed = (self.env['ir.config_parameter'].sudo().get_param(
            'afip_iibb.allowed_domains', ''
        ) or '').strip()
        if allowed:
            allowed_list = [d.strip().lower() for d in allowed.split(",") if d.strip()]
            ok = (host in allowed_list) or any(host.endswith("." + d) for d in allowed_list)
            if not ok:
                raise UserError(_("Dominio no permitido por configuración del sistema."))

    def _download_url_to_dir(self, url, target_dir):
        """
        Descarga streaming a un archivo en target_dir.
        Guarda atómico: .tmp -> move(final).
        Devuelve final_path (con extensión real: .rar, .txt, etc.)
        """
        self.ensure_one()

        if not requests:
            raise UserError(_("Falta la librería 'requests' en el servidor."))

        url = (url or "").strip()
        self._validate_url(url)

        max_bytes = int((self.max_download_mb or 350) * 1024 * 1024)

        target_dir_real = os.path.realpath(target_dir)
        if not os.path.isdir(target_dir_real):
            os.makedirs(target_dir_real, exist_ok=True)

        # Tmp en el mismo filesystem para move atómico
        fd, tmp_path = tempfile.mkstemp(prefix="afip_iibb_", suffix=".tmp", dir=target_dir_real)
        os.close(fd)

        total = 0
        content_disp = None
        content_type = None
        try:
            with requests.get(url, stream=True, timeout=(10, 300), allow_redirects=True) as r:
                r.raise_for_status()

                content_disp = r.headers.get("Content-Disposition")
                content_type = (r.headers.get("Content-Type") or "").lower()

                cl = r.headers.get("Content-Length")
                if cl and cl.isdigit() and int(cl) > max_bytes:
                    raise UserError(_("El archivo supera el tamaño máximo permitido (%s MB).") % (self.max_download_mb or 350))

                with open(tmp_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 256):
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > max_bytes:
                            raise UserError(_("El archivo supera el tamaño máximo permitido (%s MB).") % (self.max_download_mb or 350))
                        f.write(chunk)

            # --- definir extensión real ---
            # 1) intentar por URL
            path = urllib.parse.urlparse(url).path or ""
            url_name = os.path.basename(path)
            url_ext = os.path.splitext(url_name)[1].lower() if url_name else ""

            # 2) intentar por Content-Disposition
            disp_ext = ""
            if content_disp and "filename=" in content_disp.lower():
                # content-disposition: attachment; filename="ARDJU008022026.rar"
                m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', content_disp, flags=re.I)
                if m:
                    fname = os.path.basename(m.group(1).strip())
                    disp_ext = os.path.splitext(fname)[1].lower()

            # 3) fallback por content-type
            type_ext = ""
            if "rar" in content_type:
                type_ext = ".rar"
            elif "zip" in content_type:
                type_ext = ".zip"
            elif "text/plain" in content_type:
                type_ext = ".txt"

            ext = disp_ext or url_ext or type_ext or ".bin"

            stamp = fields.Datetime.now().strftime("%Y%m%d_%H%M%S")
            final_name = self._sanitize_filename(
                f"AFIP_IIBB_{int(self.year):04d}_{int(self.month):02d}_{stamp}{ext}"
            )

            final_path = os.path.realpath(os.path.join(target_dir_real, final_name))
            if not final_path.startswith(target_dir_real + os.sep):
                raise UserError(_("Destino inválido."))

            shutil.move(tmp_path, final_path)
            return final_path

        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
            raise


    def _get_input_binary_stream(self):
        self.ensure_one()
        # URL
        target_dir = self._get_download_dir()
        saved_path = self._download_url_to_dir(self.url.strip(), target_dir)
        real_data_path = self._extract_if_needed(saved_path, target_dir)

        fb = open(real_data_path, "rb")
        return fb, True, real_data_path, saved_path, target_dir
    # ----------------- IMPORT PRINCIPAL -----------------

    def import_data(self):
        self.ensure_one()
        target_dir = None
        saved_path = None
        real_data_path = None
        # Validación año
        if self.year < 2000 or self.year > 2100:
            raise UserError(_("El año ingresado no es válido."))

        m = int(self.month)
        y = int(self.year)
        from_date = date(y, m, 1)
        to_date = date(y, m, monthrange(y, m)[1])
        t0 = time.monotonic()
        # 0) Input stream (upload o URL->disco)
        fb, close_fb, real_data_path, saved_path, target_dir = self._get_input_binary_stream()

        # 1) CUIT -> partner_id (O(1))
        partner_rows = self.env['res.partner'].with_context(active_test=False).search_read(
            [('vat', '!=', False), ('type', '=', 'contact')],
            ['id', 'vat']
        )
        partner_by_cuit = {}
        for r in partner_rows:
            c = self._norm_cuit(r.get('vat'))
            if c:
                partner_by_cuit[c] = r['id']

        _logger.info("AFIP IIBB: partners con CUIT=%s (%.2fs)",
                     len(partner_by_cuit), time.monotonic() - t0)

        # 2) Parse streaming
        delim = (self.delimiter or ';')
        cuit_i = int(self.cuit_index)
        perc_i = int(self.percepcion_index)
        ret_i = int(self.retencion_index)
        max_idx = max(cuit_i, perc_i, ret_i)

        rates_by_partner = {}  # partner_id -> (perc, ret)
        processed = 0
        matched = 0
        log_each = 200000

        try:
            f = io.TextIOWrapper(fb, encoding='latin-1', errors='replace', newline='')
            for i, line in enumerate(f, start=1):
                processed = i
                if not line:
                    continue
                parts = line.strip().split(delim)
                if len(parts) <= max_idx:
                    continue

                cuit = self._norm_cuit(parts[cuit_i])
                if not cuit:
                    continue

                pid = partner_by_cuit.get(cuit)
                if not pid:
                    continue

                rates_by_partner[pid] = (self._to_float(parts[perc_i]), self._to_float(parts[ret_i]))
                matched += 1

                if i % log_each == 0:
                    _logger.info("AFIP IIBB: lineas=%s matches=%s partners_matcheados=%s (%.2fs)",
                                 i, matched, len(rates_by_partner), time.monotonic() - t0)
        finally:
            try:
                f.detach()
            except Exception:
                pass
            if close_fb:
                fb.close()


        _logger.info(
            "AFIP IIBB: parse fin lineas=%s partners_matcheados=%s (%.2fs) archivo=%s",
            processed, len(rates_by_partner), time.monotonic() - t0, saved_path or "upload"
        )

        # Limpieza de carpeta extraída (solo si vino de URL rar)
        try:
            if saved_path and target_dir and saved_path.lower().endswith(".rar"):
                base = os.path.splitext(os.path.basename(saved_path))[0]
                extract_dir = os.path.join(target_dir, f"{base}_extracted")
                if os.path.isdir(extract_dir):
                    shutil.rmtree(extract_dir)
        except Exception:
            _logger.warning("No se pudo limpiar carpeta extraída", exc_info=True)

        if not rates_by_partner:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Sin coincidencias',
                    'message': 'No se encontraron CUIT del padrón en contactos.',
                    'type': 'warning',
                    'sticky': True,
                    'timeout': 12000,
                    'next': {'type': 'ir.actions.act_window_close'}
                }
            }

        # 3) Preparar filas para temp table (partner x company)
        now = fields.Datetime.now()
        uid = self.env.uid
        sql_rows = []
        for pid, (perc, ret) in rates_by_partner.items():
            for company_id in COMPANY_IDS:
                sql_rows.append((pid, self.tag_id, company_id, from_date, to_date, perc, ret, uid, now, uid, now))

        cr = self.env.cr

        # 4) Temp table
        cr.execute("DROP TABLE IF EXISTS tmp_agip_alicuot")
        cr.execute("""
            CREATE TEMP TABLE tmp_agip_alicuot (
                partner_id integer,
                tag_id integer,
                company_id integer,
                from_date date,
                to_date date,
                alicuota_percepcion numeric(16,6),
                alicuota_retencion numeric(16,6),
                create_uid integer,
                create_date timestamp,
                write_uid integer,
                write_date timestamp
            ) ON COMMIT DROP
        """)

        # Bulk insert temp
        execute_values(cr, """
            INSERT INTO tmp_agip_alicuot
            (partner_id, tag_id, company_id, from_date, to_date,
             alicuota_percepcion, alicuota_retencion,
             create_uid, create_date, write_uid, write_date)
            VALUES %s
        """, sql_rows, page_size=10000)

        # Índice y estadísticas sobre la temp
        cr.execute("""
            CREATE INDEX tmp_agip_alicuot_match_idx
            ON tmp_agip_alicuot (partner_id, tag_id, company_id, from_date, to_date)
        """)
        cr.execute("ANALYZE tmp_agip_alicuot")

        _logger.info("AFIP IIBB: temp cargada rows=%s (%.2fs)", len(sql_rows), time.monotonic() - t0)

        # 5) UPDATE masivo
        cr.execute("""
            UPDATE res_partner_arba_alicuot t
            SET
                alicuota_percepcion = s.alicuota_percepcion,
                alicuota_retencion  = s.alicuota_retencion,
                write_uid = s.write_uid,
                write_date = s.write_date
            FROM tmp_agip_alicuot s
            WHERE t.partner_id = s.partner_id
              AND t.tag_id = s.tag_id
              AND t.company_id = s.company_id
              AND t.from_date = s.from_date
              AND t.to_date = s.to_date
        """)
        updated = cr.rowcount
        _logger.info("AFIP IIBB: UPDATE ok updated=%s (%.2fs)", updated, time.monotonic() - t0)

        # 6) INSERT masivo (solo faltantes)
        cr.execute("""
            INSERT INTO res_partner_arba_alicuot
            (partner_id, tag_id, company_id, from_date, to_date,
             alicuota_percepcion, alicuota_retencion,
             create_uid, create_date, write_uid, write_date)
            SELECT
                s.partner_id, s.tag_id, s.company_id, s.from_date, s.to_date,
                s.alicuota_percepcion, s.alicuota_retencion,
                s.create_uid, s.create_date, s.write_uid, s.write_date
            FROM tmp_agip_alicuot s
            WHERE NOT EXISTS (
                SELECT 1
                FROM res_partner_arba_alicuot t
                WHERE t.partner_id = s.partner_id
                  AND t.tag_id = s.tag_id
                  AND t.company_id = s.company_id
                  AND t.from_date = s.from_date
                  AND t.to_date = s.to_date
            )
        """)
        inserted = cr.rowcount
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Importación completada',
                'message': (
                    "Se actualizaron y crearon las alícuotas de impuestos brutos según el padrón de AFIP.\n"
                    f"Actualizados: {updated} | Insertados: {inserted}"
                ),
                'type': 'success',
                'sticky': True,
                'timeout': 20000,
                'next': {'type': 'ir.actions.act_window_close'}
            }
        }
