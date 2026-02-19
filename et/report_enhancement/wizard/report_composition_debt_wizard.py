# -*- coding: utf-8 -*-
import io, xlsxwriter, base64
from collections import defaultdict
from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


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
        return {
            'type': 'ir.actions.act_url',
            'url': f"data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{xlsx_data.encode().decode('utf-8')}",
            'target': 'new',
        }   
        
        
        
    # ---------------------------
    #
    # 1) DATA
    # 
    # ---------------------------
    def _get_lines(self, partner_ids):
        data = []
        domain = [("move_type", "in", ["out_invoice", "out_refund"]), ("state", "=", "posted")]
        if partner_ids:
            domain += [("partner_id", "in", partner_ids)]
            
        account_moves = self.env["account.move"].search(domain)
        if not account_moves:
            raise ValidationError(_("No se encontraron líneas de factura para el período seleccionado."))   
        
        for move in account_moves:
            data.append({
                "partner": move.partner_id.display_name,
                "invoice_number": move.name,
                "date": move.invoice_date,
                "debit": move.amount_total,
                "credit": 0.0,
                "subtotal": move.amount_total,
                "company": move.company_id.display_name
            })
            
        # añadir los recibos de cliente
        account_payment_domain = [("payment_type", "=", "inbound"), ("state", "=", "posted")]
        if partner_ids:
            account_payment_domain += [("partner_id", "in", partner_ids)]
        account_payment_groups = self.env["account.payment.group"].search(account_payment_domain)
        if account_payment_groups:
            for group in account_payment_groups:
                data.append({
                    "partner": group.partner_id.display_name,
                    "invoice_number": group.display_name,
                    "date": group.payment_date,
                    "debit": 0.0,
                    "credit": group.payments_amount,
                    "subtotal": -group.payments_amount,
                    "company": group.company_id.display_name
                })
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
        ws_composition_debt.set_column(3, 3, 15)      # Debe
        ws_composition_debt.set_column(4, 4, 10)      # Haber
        ws_composition_debt.set_column(5, 5, 15)      # Total Documento
        ws_composition_debt.set_column(6, 6, 30)      # Empresa
        # Alto de filas de título/encabezado
        ws_composition_debt.set_row(0, 20)
        ws_composition_debt.set_row(1, 18)
        headers_salida = ['CLIENTE', 'FECHA', 'DOCUMENTO', 'DEBE', 'HABER', 'TOTAL DOCUMENTO', 'EMPRESA']
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
            ws_composition_debt.write(row, 6, line['company'], fmt_text_l)
            row += 1
        #totales
        ws_composition_debt.write(row, 2, 'TOTAL', fmt_text_bold_l)
        ws_composition_debt.write(row, 3, total_debe, fmt_total_contab)
        ws_composition_debt.write(row, 4, total_haber, fmt_total_contab)
        ws_composition_debt.write(row, 5, total_subtotal, fmt_total_contab)
        workbook.close()
        output.seek(0)
        return output.read()
    