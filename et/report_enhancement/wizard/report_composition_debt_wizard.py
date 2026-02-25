# -*- coding: utf-8 -*-
import io, xlsxwriter, base64
from collections import defaultdict
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import date as pydate

class ReportCompositionDebtWizard(models.TransientModel):
    """Reporte de composicion de deuda Cliente."""

    _name = "report.composition.debt.wizard"
    _description = "Reporte de composicion de deuda Cliente"

    partner_id = fields.Many2one('res.partner', string='Cliente', help='Seleccionar un Cliente para filtrar', domain=[('is_company', '=', True)])
    parent_ids = fields.Many2many('res.partner', string='Cliente Relacionado', help='Filtrar por empresa padre y los que pertenecen a ella',
                                domain=[('company_type', '=', 'person'), ('parent_id', '!=', False)])
    
    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        self.parent_ids = False
        if self.partner_id:
            parent_ids = self.env['res.partner'].search([('parent_id', '=', self.partner_id.id)])
            if parent_ids:
                self.parent_ids = parent_ids
            else:
                self.parent_ids = False
            return {'domain': {'parent_ids': [('parent_id', '=', self.partner_id.id)]}}

    def action_export_xlsx(self):
        self.ensure_one()
        partner_ids = self.parent_ids.ids if self.parent_ids else []
        partner_ids = partner_ids + [self.partner_id.id] if self.partner_id else partner_ids
        lines = self._get_lines(partner_ids)
        if not lines:
            raise UserError(_("No hay datos para el rango seleccionado."))
        
        #ordenar por fecha ascendente
        lines = sorted(lines, key=lambda x: x['date'])
        xlsx_data = self._build_xlsx(lines)
        filename = f"Reporte-composicion-deuda-{self.partner_id.display_name}.xlsx"
        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(xlsx_data),
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }
        
        
    # ---------------------------
    #
    # 1) DATA
    # 
    # ---------------------------
    def _get_lines(self, partner_ids):
        lines = []

        # FACTURAS / NC CLIENTE
        move_domain = [
            ("move_type", "in", ["out_invoice", "out_refund"]),
            ("state", "=", "posted"),
        ]
        if partner_ids:
            move_domain += [("partner_id", "in", partner_ids)]

        moves = self.env["account.move"].search(move_domain, order="partner_id, company_id, currency_id, invoice_date, id")
        if not moves:
            raise ValidationError(_("No se encontraron líneas de factura para el período seleccionado."))

        for move in moves:
            # fecha consistente
            d = move.invoice_date or move.date

            debit = move.amount_total if move.move_type == "out_invoice" else 0.0
            credit = move.amount_total if move.move_type == "out_refund" else 0.0

            # importe con signo para saldo acumulado (en moneda del documento)
            signed_amount = move.amount_total if move.move_type == "out_invoice" else -move.amount_total

            lines.append({
                "key": (move.partner_id.id, move.company_id.id, move.currency_id.id),
                "sort_date": d or pydate.min,
                "partner": move.partner_id.display_name,
                "invoice_number": move.name,
                "date": d,
                "debit": debit,
                "credit": credit,
                "subtotal": signed_amount,
                "company": move.company_id.display_name,
                # auxiliares internos
                "_signed_amount": signed_amount,
            })

        # RECIBOS (PAYMENT GROUP)
        pay_domain = [("partner_type", "=", "customer"), ("state", "=", "posted")]
        if partner_ids:
            pay_domain += [("partner_id", "in", partner_ids)]

        groups = self.env["account.payment.group"].search(pay_domain, order="partner_id, company_id, payment_date, id")
        for group in groups:
            d = group.payment_date

            # en general payments_amount reduce deuda
            signed_amount = -group.payments_amount

            # ojo: si payment group tiene moneda, úsala; si no, caer a company currency
            currency = getattr(group, "currency_id", False) or group.company_id.currency_id

            lines.append({
                "key": (group.partner_id.id, group.company_id.id, currency.id),
                "sort_date": d or pydate.min,
                "partner": group.partner_id.display_name,
                "invoice_number": group.display_name,
                "date": d,
                "debit": 0.0,
                "credit": group.payments_amount,
                "subtotal": signed_amount,
                "company": group.company_id.display_name,
                "_signed_amount": signed_amount,
            })

        # ORDEN + SALDO ACUMULADO
        lines.sort(key=lambda x: (x["key"], x["sort_date"]))

        running = defaultdict(float)
        data = []
        for ln in lines:
            k = ln.pop("key")
            amt = ln.pop("_signed_amount")
            running[k] += amt
            ln["pending_balance"] = running[k]   # <- saldo gradual/acumulado
            ln.pop("sort_date", None)
            data.append(ln)

        return data
    
    
    # ---------------------------
    #
    # 2) XLSX
    #
    # ---------------------------
    def _build_xlsx(self, lines):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})

        # =========================
        # FORMATOS
        # =========================
        fmt_title = workbook.add_format({
            'bold': True,
            'font_color': '#FFFFFF',
            'bg_color': '#000000',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#FFFFFF',
        })

        fmt_header = workbook.add_format({
            'bold': True,
            'font_color': '#FFFFFF',
            'bg_color': '#000000',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#FFFFFF',
        })
        fmt_total = workbook.add_format({
            'bold': True,
            'font_color': '#FFFFFF',
            'bg_color': '#000000',
            'align': 'right',
            'valign': 'vcenter',
            'border': 1,
            'border_color': '#FFFFFF',
        })
        fmt_text_l = workbook.add_format({'border': 1, 'align': 'left', 'valign': 'vcenter'})
        fmt_text_c = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter'})
        fmt_int = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0'})
        fmt_tr_int_no_border = workbook.add_format({'bold': True, 'align': 'right', 'valign': 'vcenter', 'num_format': '0'})
        fmt_total_bultos = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0.00', 'bold': True})
        fmt_dec = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '0.00'})
        fmt_dec_no_border_c = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'num_format': '0.00'})
        fmt_dec_no_border_l = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'num_format': '0.00'})
        fmt_text_bold_l = workbook.add_format({'align': 'right', 'valign': 'vcenter', 'bold': True})
        #formato contabilidad
        fmt_contab = workbook.add_format({'border': 1, 'align': 'center', 'valign': 'vcenter', 'num_format': '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'})
        fmt_total_contab = workbook.add_format({'border': 1, 'bold': True, 'align': 'center', 'valign': 'vcenter', 'num_format': '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'})
        fmt_tr_contab_no_border = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter', 'num_format': '_($* #,##0.00_);_($* (#,##0.00);_($* "-"??_);_(@_)'})
        
        
        
        fmt_title = workbook.add_format({"bold": True, "font_size": 16, "align": "center", "valign": "vcenter"})
        fmt_h = workbook.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
        fmt_txt = workbook.add_format({"border": 1})
        fmt_int = workbook.add_format({"num_format": "#,##0;[Red]-#,##0", "border": 1})
        fmt_decimal = workbook.add_format({"num_format": "#,##0.00;[Red]-#,##0.00", "border": 1})
        fmt_money = workbook.add_format({
            "border": 1,
            "align": "center",
            "valign": "vcenter",
            "num_format": '_($* #,##0.00_);[Red]_($* -#,##0.00_);_($* "-"??_);_(@_)'
        })

        # Sheets
        ws_composition_debt = workbook.add_worksheet("Composición de Deuda")

        ws_composition_debt.merge_range(0, 0, 0, 6, ('REPORTE DE COMPOSICIÓN DE DEUDA DEL CLIENTE'), fmt_title)
        ws_composition_debt.set_column(0, 0, 60)      # Cliente
        ws_composition_debt.set_column(1, 1, 15)      # Fecha
        ws_composition_debt.set_column(2, 2, 30)      # Documento
        ws_composition_debt.set_column(3, 3, 25)      # Debe
        ws_composition_debt.set_column(4, 4, 25)      # Haber
        ws_composition_debt.set_column(5, 5, 30)      # Total Documento
        ws_composition_debt.set_column(6, 6, 30)      # Saldo Pendiente
        ws_composition_debt.set_column(7, 7, 30)      # Empresa
        # Alto de filas de título/encabezado
        ws_composition_debt.set_row(0, 20)
        ws_composition_debt.set_row(1, 18)
        headers_salida = ['CLIENTE', 'FECHA', 'DOCUMENTO', 'DEBE', 'HABER', 'TOTAL DOCUMENTO', 'SALDO PENDIENTE', 'EMPRESA']
        for col, h in enumerate(headers_salida):
            ws_composition_debt.write(1, col, h, fmt_header)
        row = 2
        total_debe = total_haber = total_subtotal = 0.0
        for line in lines:
            total_debe += line['debit']
            total_haber += line['credit']
            total_subtotal += line['subtotal']
            ws_composition_debt.write(row, 0, line['partner'], fmt_text_l)
            ws_composition_debt.write(row, 1, line['date'].strftime('%d/%m/%Y'), fmt_text_c)
            ws_composition_debt.write(row, 2, line['invoice_number'], fmt_text_l)
            ws_composition_debt.write(row, 3, line['debit'], fmt_contab)
            ws_composition_debt.write(row, 4, line['credit'], fmt_contab)
            ws_composition_debt.write(row, 5, line['subtotal'], fmt_money)
            ws_composition_debt.write(row, 6, line['pending_balance'], fmt_money)
            ws_composition_debt.write(row, 7, line['company'], fmt_text_l)
            row += 1
        #totales
        ws_composition_debt.write(row, 3, 'TOTAL', fmt_text_bold_l)
        ws_composition_debt.write(row, 4, total_debe, fmt_total_contab)
        ws_composition_debt.write(row, 5, total_haber, fmt_total_contab)
        ws_composition_debt.write(row, 6, total_subtotal, fmt_total_contab)
        workbook.close()
        output.seek(0)
        return output.read()
    