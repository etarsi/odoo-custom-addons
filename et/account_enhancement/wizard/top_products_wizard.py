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

    def default_get(self, fields):
        res = super().default_get(fields)
        if res['temporada'] == 't_nino_2025':
            res['date_start'] = date(2025, 3, 1)
            res['date_end'] = date(2025, 8, 31)
        elif res['temporada'] == 't_nav_2025':
            res['date_start'] = date(2025, 9, 1)
            res['date_end'] = date(2026, 2, 28)        
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
            if not product:
                continue
            data.append({
                "invoice_date": move.invoice_date,
                "invoice_number": move.name,
                "partner": move.partner_id.display_name,
                "company": move.company_id.display_name,
                "product": product.display_name,
                "sku": product.default_code,
                "category": product.categ_id.display_name,
                "uom": 'Default UoM',  # podrías usar product.uom_id.name o similar
                "type": "refund" if move.move_type == "out_refund" else "invoice",
                "qty": line.quantity,
                "price_unit": line.price_unit,
                "discount": line.discount,  # suponemos que es %
                "subtotal": line.price_subtotal,  # sin impuestos
            })
        return data

    # ---------------------------
    # 2) XLSX builder
    # ---------------------------
    def _build_xlsx(self, lines):
        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})

        # Formats
        fmt_title = wb.add_format({"bold": True, "font_size": 16})
        fmt_h = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
        fmt_txt = wb.add_format({"border": 1})
        fmt_int = wb.add_format({"num_format": "0", "border": 1})
        fmt_money = wb.add_format({"num_format": "#,##0.00", "border": 1})
        fmt_pct = wb.add_format({"num_format": "0.00%", "border": 1})
        fmt_date = wb.add_format({"num_format": "yyyy-mm-dd", "border": 1})
        fmt_note = wb.add_format({"font_color": "#555555", "italic": True})

        # Sheets
        ws_r = wb.add_worksheet("Resumen")
        ws_dash = wb.add_worksheet("Dashboard")

        # -------------------------
        # 1) Agregación (desde lines)
        # -------------------------
        agg = defaultdict(lambda: {
            "product": "",
            "sku": "",
            "category": "",
            "ventas": 0.0,
            "qty": 0.0,
        })

        for ln in lines:
            typ = ln.get("type") or "invoice"
            is_refund = (typ == "refund")
            if is_refund and not self.include_refunds:
                continue

            signo = -1 if is_refund else 1

            product = (ln.get("product") or "").strip()
            if not product:
                continue

            key = product  # si querés diferenciar por SKU: key = (product, ln.get("sku"))
            rec = agg[key]
            rec["product"] = product
            rec["sku"] = (ln.get("sku") or "").strip()
            rec["category"] = (ln.get("category") or "").strip()

            qty = float(ln.get("qty") or 0.0) * signo
            subtotal = float(ln.get("subtotal") or 0.0) * signo

            rec["qty"] += qty
            rec["ventas"] += subtotal

        if not agg:
            raise UserError(_("No hay datos luego de aplicar filtros (ej. excluir NC)."))

        ordered = sorted(agg.values(), key=lambda x: x["ventas"], reverse=True)

        total_ventas = sum(r["ventas"] for r in ordered)
        total_qty = sum(r["qty"] for r in ordered)

        # -------------------------
        # 2) Resumen
        # -------------------------
        ws_r.set_column("A:A", 6)   # Rank
        ws_r.set_column("B:B", 35)  # Producto
        ws_r.set_column("C:C", 16)  # SKU
        ws_r.set_column("D:D", 22)  # Categoría
        ws_r.set_column("E:E", 18)  # Ventas
        ws_r.set_column("F:F", 16)  # Qty
        ws_r.set_column("G:G", 14)  # % total
        ws_r.set_column("H:H", 14)  # % acum

        ws_r.write("A1", "Resumen por producto", fmt_title)
        ws_r.write("A3", "Temporada", fmt_h)
        ws_r.write("B3", dict(self._fields["temporada"].selection).get(self.temporada, self.temporada), fmt_txt)

        ws_r.write("D3", "Fecha desde", fmt_h)
        if self.date_start:
            ws_r.write_datetime("E3", fields.Date.to_date(self.date_start), fmt_date)
        ws_r.write("F3", "Fecha hasta", fmt_h)
        if self.date_end:
            ws_r.write_datetime("G3", fields.Date.to_date(self.date_end), fmt_date)

        headers = ["Rank", "Producto", "SKU", "Categoría", "Ventas Netas", "Cantidad Neta", "% sobre total", "% acumulado"]
        header_row = 4
        for c, h in enumerate(headers):
            ws_r.write(header_row, c, h, fmt_h)

        data_start_row = header_row + 1  # fila donde empieza la data (0-based)
        acum = 0.0
        for i, r in enumerate(ordered, start=1):
            row = data_start_row + (i - 1)
            ventas = r["ventas"]
            qty = r["qty"]

            pct_total = (ventas / total_ventas) if total_ventas else 0.0
            acum += pct_total

            ws_r.write_number(row, 0, i, fmt_int)
            ws_r.write(row, 1, r["product"], fmt_txt)
            ws_r.write(row, 2, r["sku"], fmt_txt)
            ws_r.write(row, 3, r["category"], fmt_txt)
            ws_r.write_number(row, 4, ventas, fmt_money)
            ws_r.write_number(row, 5, qty, fmt_int)
            ws_r.write_number(row, 6, pct_total, fmt_pct)
            ws_r.write_number(row, 7, acum, fmt_pct)

        total_row = data_start_row + len(ordered) + 1
        ws_r.write(total_row, 3, "TOTAL", fmt_h)
        ws_r.write_number(total_row, 4, total_ventas, fmt_money)
        ws_r.write_number(total_row, 5, total_qty, fmt_int)
        ws_r.write(total_row, 6, "", fmt_h)
        ws_r.write(total_row, 7, "", fmt_h)

        # -------------------------
        # 3) Dashboard (KPIs + Charts)
        # -------------------------
        ws_dash.set_column("A:A", 2)
        ws_dash.set_column("B:B", 40)
        ws_dash.set_column("C:D", 22)

        ws_dash.write("B1", "Dashboard - Top Productos Facturados", fmt_title)
        ws_dash.write("B3", "Ventas netas totales", fmt_h)
        ws_dash.write_number("C3", total_ventas, fmt_money)

        ws_dash.write("B4", "Unidades netas totales", fmt_h)
        ws_dash.write_number("C4", total_qty, fmt_int)

        ws_dash.write("B5", "Incluye Notas de Crédito (netea)", fmt_h)
        ws_dash.write("C5", "Sí" if self.include_refunds else "No", fmt_txt)

        # Top N para gráficos
        top_n = max(int(self.top_n or 20), 1)
        top_n = min(top_n, len(ordered))

        # Rangos en Resumen:
        # categorías (Producto) = col B (index 1)
        # ventas = col E (index 4)
        # qty = col F (index 5)
        first = data_start_row
        last = data_start_row + top_n - 1

        # Chart Top ventas (bar horizontal)
        chart_v = wb.add_chart({"type": "bar"})
        chart_v.add_series({
            "name": "Ventas Netas",
            "categories": ["Resumen", first, 1, last, 1],
            "values": ["Resumen", first, 4, last, 4],
        })
        chart_v.set_title({"name": f"Top {top_n} por Ventas Netas"})
        chart_v.set_legend({"none": True})
        ws_dash.insert_chart("B7", chart_v, {"x_scale": 1.35, "y_scale": 1.25})

        # Chart Top unidades
        chart_q = wb.add_chart({"type": "bar"})
        chart_q.add_series({
            "name": "Cantidad Neta",
            "categories": ["Resumen", first, 1, last, 1],
            "values": ["Resumen", first, 5, last, 5],
        })
        chart_q.set_title({"name": f"Top {top_n} por Cantidad Neta"})
        chart_q.set_legend({"none": True})
        ws_dash.insert_chart("B23", chart_q, {"x_scale": 1.35, "y_scale": 1.25})

        # Pareto: columnas (ventas) + línea (% acumulado)
        chart_p = wb.add_chart({"type": "column"})
        chart_p.add_series({
            "name": "Ventas Netas",
            "categories": ["Resumen", first, 1, last, 1],
            "values": ["Resumen", first, 4, last, 4],
        })
        chart_line = wb.add_chart({"type": "line"})
        chart_line.add_series({
            "name": "% acumulado",
            "categories": ["Resumen", first, 1, last, 1],
            "values": ["Resumen", first, 7, last, 7],
            "y2_axis": True,
        })
        chart_p.combine(chart_line)
        chart_p.set_title({"name": f"Pareto Top {top_n}"})
        chart_p.set_y2_axis({"min": 0, "max": 1})
        ws_dash.insert_chart("F7", chart_p, {"x_scale": 1.25, "y_scale": 1.25})

        wb.close()
        output.seek(0)
        return output.read()

