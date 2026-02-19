# -*- coding: utf-8 -*-
import io, xlsxwriter, base64
from collections import defaultdict
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class TopProductsInvoicedWizard(models.TransientModel):
    _name = "top.products.invoiced.wizard"
    _description = "Wizard Top Productos Facturados (XLSX)"

    temporada = fields.Selection(string='Temporada', selection=[
        ('t_all', 'Todas las Temporadas'),
        ('t_nino_2025', 'Temporada Niño 2025'),
        ('t_nav_2025', 'Temporada Navidad 2025'),
    ], required=True, default='t_nav_2025', help='Seleccionar la temporada para el reporte')  
    date_start = fields.Date(string="Fecha desde", readonly=True)
    date_end = fields.Date(string="Fecha hasta", readonly=True)
    top_n = fields.Integer(string="Top N", default=20)
    include_refunds = fields.Boolean(string="Incluir Notas de Crédito", default=True)

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        temporada = res.get("temporada") or "t_nav_2025"
        if temporada == "t_nino_2025":
            res.update({"date_start": date(2025, 3, 1), "date_end": date(2025, 8, 31)})
        elif temporada == "t_nav_2025":
            res.update({"date_start": date(2025, 9, 1), "date_end": date(2026, 2, 28)})
        return res
        
    @api.onchange('temporada')
    def _onchange_temporada(self):
        if self.temporada == 't_nino_2025':
            self.date_start = date(2025, 3, 1)
            self.date_end = date(2025, 8, 31)
        elif self.temporada == 't_nav_2025':
            self.date_start = date(2025, 9, 1)
            self.date_end = date(2026, 2, 28)        
        else:
            self.date_start = False
            self.date_end = False

    def action_export_xlsx(self):
        self.ensure_one()

        lines = self._get_lines()
        if not lines:
            raise UserError(_("No hay datos para el rango seleccionado."))

        xlsx_content = self._build_xlsx(lines)

        filename = f"Top_Productos_{self.temporada}.xlsx"
        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(xlsx_content),
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

    # ---------------------------
    # 1) DATA (tu implementación)
    # ---------------------------
    def _get_lines(self):
        """
        Devuelve lista de dicts con las columnas que usaremos en 01_Datos.

        Reemplazá esto por tu query real (account.move.line + move, etc).
        """
        data = []
        domain = [("move_id.move_type", "in", ["out_invoice", "out_refund"]), ("move_id.state", "=", "posted")]
        if self.temporada == "t_nino_2025":
            domain += [('create_date', '>=', date(2025, 3, 1)), ('create_date', '<=', date(2025, 8, 31))]
        elif self.temporada == 't_nav_2025':
            domain += [('create_date', '>=', date(2025, 9, 1)), ('create_date', '<=', date(2026, 2, 28))]
            
        account_move_lines = self.env["account.move.line"].search(domain)
        if not account_move_lines:
            raise ValidationError(_("No se encontraron líneas de factura para el período seleccionado."))   
        
        for line in account_move_lines:
            move = line.move_id
            product = line.product_id
            if not product or not product.default_code:
                continue
            data.append({
                "invoice_date": move.invoice_date,
                "invoice_number": move.name,
                "partner": move.partner_id.display_name,
                "company": move.company_id.display_name,
                "product": product.name,
                "default_code": product.default_code,
                "category": product.categ_id.display_name,
                "type": "refund" if move.move_type == "out_refund" else "invoice",
                "qty": line.quantity,
                "price_unit": line.price_unit,
                "discount": line.discount,  # suponemos que es %
                "subtotal": line.price_subtotal,  # sin impuestos
            })
        return data
    
    def _normalize_code_for_report(self, code):
        code = (code or "").strip()

        # Regla automática: quitar prefijo legal '9' en códigos numéricos
        # Variante "agresiva": si empieza con 9 y lo que sigue es numérico, lo quita
        if code.startswith("9") and code[1:].isdigit():
            return code[1:]

        return code

    # ---------------------------
    # 2) XLSX builder
    # ---------------------------
    def _build_xlsx(self, lines):
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})

        # Formats
        fmt_title = wb.add_format({"bold": True, "font_size": 16, "align": "center", "valign": "vcenter"})
        fmt_h = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
        fmt_txt = wb.add_format({"border": 1})
        fmt_int = wb.add_format({"num_format": "0", "border": 1})
        fmt_money = wb.add_format({"num_format": "#,##0.00", "border": 1})
        fmt_pct = wb.add_format({"num_format": "0.00%", "border": 1})
        fmt_date = wb.add_format({"num_format": "yyyy-mm-dd", "border": 1})
        fmt_note = wb.add_format({"font_color": "#555555", "italic": True})

        # Sheets
        ws_r = wb.add_worksheet("Resumen")
        ws_dash = wb.add_worksheet("Grafico")

        # -------------------------
        # 1) Agregación (desde lines) con código normalizado
        # -------------------------
        agg = defaultdict(lambda: {
            "product": "",
            "default_code": "",
            "category": "",
            "ventas": 0.0,
            "qty": 0.0,
            "name_count": defaultdict(int),  # para elegir nombre más repetido
        })

        for ln in lines:
            typ = ln.get("type") or "invoice"
            is_refund = (typ == "refund")
            if is_refund and not self.include_refunds:
                continue

            signo = -1 if is_refund else 1

            product = (ln.get("product") or "").strip()
            raw_code = (ln.get("default_code") or "").strip()
            if not raw_code:
                continue

            # 👇 unión masiva: 9xxxx -> xxxx
            group_code = self._normalize_code_for_report(raw_code)

            key = group_code
            rec = agg[key]

            rec["default_code"] = group_code
            rec["category"] = (ln.get("category") or "").strip()

            # elegimos el nombre más frecuente dentro del grupo
            if product:
                rec["name_count"][product] += 1

            qty = float(ln.get("qty") or 0.0) * signo
            subtotal = float(ln.get("subtotal") or 0.0) * signo

            rec["qty"] += qty
            rec["ventas"] += subtotal

        if not agg:
            raise UserError(_("No hay datos luego de aplicar filtros (ej. excluir NC)."))

        # consolidar nombre por grupo: el más repetido
        ordered = []
        for rec in agg.values():
            if rec["name_count"]:
                rec["product"] = max(rec["name_count"].items(), key=lambda kv: kv[1])[0]
            else:
                rec["product"] = rec["default_code"]
            ordered.append(rec)

        ordered = sorted(ordered, key=lambda x: x["ventas"], reverse=True)

        total_ventas = sum(r["ventas"] for r in ordered)
        total_qty = sum(r["qty"] for r in ordered)

        # -------------------------
        # 2) Resumen (con % y acumulado)
        # -------------------------
        ws_r.set_column("A:A", 6)   # Rank
        ws_r.set_column("B:B", 20)  # Código
        ws_r.set_column("C:C", 60)  # Producto
        ws_r.set_column("D:D", 40)  # Categoría
        ws_r.set_column("E:E", 20)  # Ventas
        ws_r.set_column("F:F", 20)  # Qty
        ws_r.set_column("G:G", 14)  # % total
        ws_r.set_column("H:H", 14)  # % acum

        ws_r.merge_range(
            "A1:F1",
            "Resumen de Productos Facturados - %s" % dict(self._fields["temporada"].selection).get(self.temporada, self.temporada),
            fmt_title
        )
        if self.date_start or self.date_end:
            ws_r.write("D3", "Fecha desde", fmt_h)
            if self.date_start:
                ws_r.write_datetime("E3", fields.Date.to_date(self.date_start), fmt_date)
            ws_r.write("D4", "Fecha hasta", fmt_h)
            if self.date_end:
                ws_r.write_datetime("E4", fields.Date.to_date(self.date_end), fmt_date)

        headers = ["Rank", "Código", "Producto", "Categoría", "Ventas Totales", "Cantidad Total"]
        header_row = 5
        for c, h in enumerate(headers):
            ws_r.write(header_row, c, h, fmt_h)

        data_start_row = header_row + 1
        acum = 0.0
        for i, r in enumerate(ordered, start=1):
            row = data_start_row + (i - 1)
            ventas = r["ventas"]
            qty = r["qty"]

            pct_total = (ventas / total_ventas) if total_ventas else 0.0
            acum += pct_total

            ws_r.write_number(row, 0, i, fmt_int)
            ws_r.write(row, 1, r["default_code"], fmt_txt)
            ws_r.write(row, 2, r["product"], fmt_txt)
            ws_r.write(row, 3, r["category"], fmt_txt)
            ws_r.write_number(row, 4, ventas, fmt_money)
            ws_r.write_number(row, 5, qty, fmt_int)

        total_row = data_start_row + len(ordered) + 1
        ws_r.write(total_row, 3, "TOTAL", fmt_h)
        ws_r.write_number(total_row, 4, total_ventas, fmt_money)
        ws_r.write_number(total_row, 5, total_qty, fmt_int)

        # -------------------------
        # 3) Gráficos (arreglado: índices correctos)
        # -------------------------
        top_n = max(int(self.top_n or 20), 1)
        top_n = min(top_n, len(ordered))

        first = data_start_row
        last = data_start_row + top_n - 1

        # Top ventas: categorías = Producto (col C -> idx 2), valores = Ventas (col E -> idx 4)
        chart_v = wb.add_chart({"type": "bar"})
        chart_v.add_series({
            "name": "Ventas",
            "categories": ["Resumen", first, 2, last, 2],
            "values": ["Resumen", first, 4, last, 4],
        })
        chart_v.set_title({"name": f"Top {top_n} por Ventas"})
        chart_v.set_legend({"none": True})
        chart_v.set_size({"width": 1000, "height": 450})

        # Top cantidad: valores = Qty (col F -> idx 5)
        chart_q = wb.add_chart({"type": "bar"})
        chart_q.add_series({
            "name": "Cantidad",
            "categories": ["Resumen", first, 2, last, 2],
            "values": ["Resumen", first, 5, last, 5],
        })
        chart_q.set_title({"name": f"Top {top_n} por Cantidad"})
        chart_q.set_legend({"none": True})
        chart_q.set_size({"width": 1000, "height": 450})

        # Pareto: % acumulado (col H -> idx 7)
        chart_p = wb.add_chart({"type": "column"})
        chart_p.add_series({
            "name": "Ventas",
            "categories": ["Resumen", first, 2, last, 2],
            "values": ["Resumen", first, 4, last, 4],
        })
        chart_line = wb.add_chart({"type": "line"})
        chart_line.add_series({
            "name": "% acumulado",
            "categories": ["Resumen", first, 2, last, 2],
            "values": ["Resumen", first, 7, last, 7],
            "y2_axis": True,
        })
        chart_p.combine(chart_line)
        chart_p.set_title({"name": f"Pareto Top {top_n}"})
        chart_p.set_y2_axis({"min": 0, "max": 1})
        chart_p.set_size({"width": 560, "height": 320})

        ws_dash.insert_chart("B7", chart_v, {"x_offset": 10, "y_offset": 5})
        ws_dash.insert_chart("B27", chart_q, {"x_offset": 10, "y_offset": 5})
        ws_dash.insert_chart("K7", chart_p, {"x_offset": 10, "y_offset": 5})

        wb.close()
        output.seek(0)
        return output.read()