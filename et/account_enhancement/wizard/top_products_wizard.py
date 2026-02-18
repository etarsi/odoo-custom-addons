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
    top_n = fields.Integer(string="Top N", default=20)
    include_refunds = fields.Boolean(string="Incluir Notas de Crédito", default=True)

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
        fmt_date = wb.add_format({"num_format": "yyyy-mm-dd", "border": 1})
        fmt_int = wb.add_format({"num_format": "0", "border": 1})
        fmt_money = wb.add_format({"num_format": "#,##0.00", "border": 1})
        fmt_pct = wb.add_format({"num_format": "0.00%", "border": 1})
        fmt_note = wb.add_format({"font_color": "#555555", "italic": True})

        # Sheets
        ws_p = wb.add_worksheet("00_Parametros")
        ws_d = wb.add_worksheet("01_Datos")
        ws_r = wb.add_worksheet("02_Resumen")
        ws_dash = wb.add_worksheet("03_Dashboard")
        ws_top = wb.add_worksheet("04_TopN_Detalle")

        # Column widths
        ws_d.set_column("A:A", 12)
        ws_d.set_column("B:B", 22)
        ws_d.set_column("C:C", 22)
        ws_d.set_column("D:D", 18)
        ws_d.set_column("E:E", 28)
        ws_d.set_column("F:F", 14)
        ws_d.set_column("G:G", 18)
        ws_d.set_column("H:H", 10)
        ws_d.set_column("I:I", 10)
        ws_d.set_column("J:J", 14)
        ws_d.set_column("K:K", 12)
        ws_d.set_column("L:L", 14)
        ws_d.set_column("M:M", 14)
        ws_d.set_column("N:N", 14)

        # -------------------------
        # 00_Parametros
        # -------------------------
        ws_p.write("A1", "Top Productos Facturados (XLSX)", fmt_title)
        ws_p.write("A3", "Fecha desde", fmt_h); ws_p.write_datetime("B3", fields.Date.to_date(self.date_from), fmt_date)
        ws_p.write("A4", "Fecha hasta", fmt_h); ws_p.write_datetime("B4", fields.Date.to_date(self.date_to), fmt_date)
        ws_p.write("A5", "Top N", fmt_h); ws_p.write_number("B5", self.top_n or 20, fmt_int)
        ws_p.write("A6", "Incluir NC (netear)", fmt_h); ws_p.write("B6", "Sí" if self.include_refunds else "No", fmt_txt)
        ws_p.write("A8", "Definición: Ventas netas = Subtotal * Signo (Factura=1, NC=-1).", fmt_note)

        # -------------------------
        # 01_Datos
        # -------------------------
        headers = [
            "Fecha", "Nro", "Cliente", "Compañía",
            "Producto", "SKU", "Categoría", "UoM",
            "Tipo", "Signo",
            "Cantidad", "Precio Unit", "% Desc",
            "Subtotal",
            "Cantidad Neta", "Ventas Netas",
        ]
        for col, h in enumerate(headers):
            ws_d.write(0, col, h, fmt_h)

        # Normalize + write
        row = 1
        for ln in lines:
            typ = ln.get("type") or "invoice"
            is_refund = (typ == "refund")
            if is_refund and not self.include_refunds:
                continue

            signo = -1 if is_refund else 1

            inv_date = ln.get("invoice_date")
            if inv_date:
                ws_d.write_datetime(row, 0, fields.Date.to_date(inv_date), fmt_date)
            else:
                ws_d.write(row, 0, "", fmt_txt)

            ws_d.write(row, 1, ln.get("invoice_number", ""), fmt_txt)
            ws_d.write(row, 2, ln.get("partner", ""), fmt_txt)
            ws_d.write(row, 3, ln.get("company", ""), fmt_txt)
            ws_d.write(row, 4, ln.get("product", ""), fmt_txt)
            ws_d.write(row, 5, ln.get("sku", ""), fmt_txt)
            ws_d.write(row, 6, ln.get("category", ""), fmt_txt)
            ws_d.write(row, 7, ln.get("uom", ""), fmt_txt)
            ws_d.write(row, 8, "NC" if is_refund else "Factura", fmt_txt)
            ws_d.write_number(row, 9, signo, fmt_int)

            qty = float(ln.get("qty") or 0.0)
            price_unit = float(ln.get("price_unit") or 0.0)
            disc = float(ln.get("discount") or 0.0)
            subtotal = float(ln.get("subtotal") or 0.0)

            ws_d.write_number(row, 10, qty, fmt_int)
            ws_d.write_number(row, 11, price_unit, fmt_money)
            ws_d.write_number(row, 12, disc / 100.0, fmt_pct)  # guardamos como %
            ws_d.write_number(row, 13, subtotal, fmt_money)

            # Cantidad Neta = Cantidad * Signo
            ws_d.write_formula(row, 14, f"=K{row+1}*J{row+1}", fmt_int)
            # Ventas Netas = Subtotal * Signo
            ws_d.write_formula(row, 15, f"=N{row+1}*J{row+1}", fmt_money)

            row += 1

        last_data_row = row - 1
        if last_data_row < 1:
            raise UserError(_("No hay datos luego de aplicar filtros (ej. excluir NC)."))

        # -------------------------
        # 02_Resumen (lista productos + SUMIFS)
        # -------------------------
        ws_r.set_column("A:A", 30)
        ws_r.set_column("B:B", 18)
        ws_r.set_column("C:C", 18)
        ws_r.set_column("D:D", 10)
        ws_r.set_column("E:E", 12)
        ws_r.set_column("F:F", 14)

        ws_r.write("A1", "Resumen por producto", fmt_title)

        rh = ["Producto", "Ventas Netas", "Cantidad Neta", "Rank $", "% sobre total", "% acumulado"]
        for c, h in enumerate(rh):
            ws_r.write(2, c, h, fmt_h)

        # productos únicos (desde líneas)
        products = sorted({(l.get("product") or "").strip() for l in lines if (l.get("product") or "").strip()})
        start_row = 3
        for i, prod in enumerate(products):
            r = start_row + i
            ws_r.write(r, 0, prod, fmt_txt)

            # SUMIFS sobre columna Producto (E) y Ventas Netas (P) / Cantidad Neta (O)
            # Datos: Producto = col 5 (E), Cantidad Neta col 15 (O), Ventas Netas col 16 (P)
            # Rango en datos: filas 2..last_data_row+1 (Excel 1-based)
            data_from = 2
            data_to = last_data_row + 1

            ws_r.write_formula(r, 1, f'=SUMIFS(01_Datos!$P${data_from}:$P${data_to},01_Datos!$E${data_from}:$E${data_to},$A{r+1})', fmt_money)
            ws_r.write_formula(r, 2, f'=SUMIFS(01_Datos!$O${data_from}:$O${data_to},01_Datos!$E${data_from}:$E${data_to},$A{r+1})', fmt_int)

        end_row = start_row + len(products) - 1

        # totales
        total_row = end_row + 2
        ws_r.write(total_row, 0, "TOTAL", fmt_h)
        ws_r.write_formula(total_row, 1, f"=SUM(B{start_row+1}:B{end_row+1})", fmt_money)
        ws_r.write_formula(total_row, 2, f"=SUM(C{start_row+1}:C{end_row+1})", fmt_int)

        # Rank, % total, % acumulado
        for r in range(start_row, end_row + 1):
            ws_r.write_formula(r, 3, f"=IF(B{r+1}=0,\"\",RANK.EQ(B{r+1},$B${start_row+1}:$B${end_row+1},0))", fmt_txt)
            ws_r.write_formula(r, 4, f"=IF($B${total_row+1}=0,0,B{r+1}/$B${total_row+1})", fmt_pct)
            if r == start_row:
                ws_r.write_formula(r, 5, f"=E{r+1}", fmt_pct)
            else:
                ws_r.write_formula(r, 5, f"=F{r}+E{r+1}", fmt_pct)

        # -------------------------
        # 04_TopN_Detalle (ordenado en Python)
        # -------------------------
        # Armamos agregados rápidos para listar ordenado (sin depender del orden en Excel)
        agg = defaultdict(lambda: {"ventas": 0.0, "qty": 0.0})
        # recalculamos usando las mismas reglas (signo)
        for ln in lines:
            typ = ln.get("type") or "invoice"
            if typ == "refund" and not self.include_refunds:
                continue
            signo = -1 if typ == "refund" else 1
            p = (ln.get("product") or "").strip()
            agg[p]["ventas"] += float(ln.get("subtotal") or 0.0) * signo
            agg[p]["qty"] += float(ln.get("qty") or 0.0) * signo

        top_n = max(int(self.top_n or 20), 1)
        ordered = sorted(agg.items(), key=lambda kv: kv[1]["ventas"], reverse=True)[:top_n]

        ws_top.set_column("A:A", 6)
        ws_top.set_column("B:B", 30)
        ws_top.set_column("C:C", 18)
        ws_top.set_column("D:D", 18)
        ws_top.write("A1", f"Top {top_n} por Ventas Netas", fmt_title)

        th = ["Rank", "Producto", "Ventas Netas", "Cantidad Neta"]
        for c, h in enumerate(th):
            ws_top.write(2, c, h, fmt_h)

        for i, (prod, vals) in enumerate(ordered, start=1):
            r = 2 + i
            ws_top.write_number(r, 0, i, fmt_int)
            ws_top.write(r, 1, prod, fmt_txt)
            ws_top.write_number(r, 2, vals["ventas"], fmt_money)
            ws_top.write_number(r, 3, vals["qty"], fmt_int)

        # -------------------------
        # 03_Dashboard (KPIs + charts)
        # -------------------------
        ws_dash.set_column("A:A", 2)
        ws_dash.set_column("B:B", 40)
        ws_dash.set_column("C:D", 20)
        ws_dash.write("B1", "Dashboard - Top Productos Facturados", fmt_title)

        # KPIs básicos desde Resumen (TOTAL)
        ws_dash.write("B3", "Ventas netas totales", fmt_h)
        ws_dash.write_formula("C3", f"=02_Resumen!B{total_row+1}", fmt_money)

        ws_dash.write("B4", "Unidades netas totales", fmt_h)
        ws_dash.write_formula("C4", f"=02_Resumen!C{total_row+1}", fmt_int)

        # Chart Top por ventas (desde TopN)
        chart_bar = wb.add_chart({"type": "bar"})
        # categorías: productos
        chart_bar.add_series({
            "name": "Ventas Netas",
            "categories": ["04_TopN_Detalle", 3, 1, 2 + len(ordered), 1],
            "values": ["04_TopN_Detalle", 3, 2, 2 + len(ordered), 2],
        })
        chart_bar.set_title({"name": f"Top {top_n} por Ventas Netas"})
        chart_bar.set_legend({"none": True})
        ws_dash.insert_chart("B6", chart_bar, {"x_scale": 1.3, "y_scale": 1.3})

        # Chart Top por unidades (desde TopN)
        chart_bar2 = wb.add_chart({"type": "bar"})
        chart_bar2.add_series({
            "name": "Cantidad Neta",
            "categories": ["04_TopN_Detalle", 3, 1, 2 + len(ordered), 1],
            "values": ["04_TopN_Detalle", 3, 3, 2 + len(ordered), 3],
        })
        chart_bar2.set_title({"name": f"Top {top_n} por Cantidad Neta"})
        chart_bar2.set_legend({"none": True})
        ws_dash.insert_chart("B22", chart_bar2, {"x_scale": 1.3, "y_scale": 1.3})

        wb.close()
        output.seek(0)
        return output.read()
