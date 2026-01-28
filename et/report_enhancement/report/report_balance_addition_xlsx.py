from odoo import models


class ReportBalanceAdditionXlsx(models.AbstractModel):
    _name = "report.report_enhancement.report_balance_addition_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "Balance de Sumas y Saldos (XLSX)"

    def generate_xlsx_report(self, workbook, data, wizards):
        wiz = wizards[:1]
        lines, totals = wiz._get_lines()

        ws = workbook.add_worksheet("Sumas y Saldos")
        bold = workbook.add_format({"bold": True})
        money = workbook.add_format({"num_format": "#,##0.00"})

        row = 0
        ws.write(row, 0, "Balance de Sumas y Saldos", bold); row += 1
        ws.write(row, 0, "Compañía", bold); ws.write(row, 1, wiz.company_id.name); row += 1
        ws.write(row, 0, "Desde", bold); ws.write(row, 1, str(wiz.date_from))
        ws.write(row, 2, "Hasta", bold); ws.write(row, 3, str(wiz.date_to)); row += 2

        headers = [
            "Cuenta", "Nombre",
            "Saldo Inicial Debe", "Saldo Inicial Haber",
            "Mov. Debe", "Mov. Haber",
            "Saldo Final Debe", "Saldo Final Haber",
        ]
        for col, h in enumerate(headers):
            ws.write(row, col, h, bold)
        row += 1

        for l in lines:
            ws.write(row, 0, l["account_code"])
            ws.write(row, 1, l["account_name"])
            ws.write_number(row, 2, l["initial_debit"], money)
            ws.write_number(row, 3, l["initial_credit"], money)
            ws.write_number(row, 4, l["period_debit"], money)
            ws.write_number(row, 5, l["period_credit"], money)
            ws.write_number(row, 6, l["ending_debit"], money)
            ws.write_number(row, 7, l["ending_credit"], money)
            row += 1

        # Totales
        ws.write(row, 0, "TOTALES", bold)
        ws.write_number(row, 2, totals["initial_debit"], money)
        ws.write_number(row, 3, totals["initial_credit"], money)
        ws.write_number(row, 4, totals["period_debit"], money)
        ws.write_number(row, 5, totals["period_credit"], money)
        ws.write_number(row, 6, totals["ending_debit"], money)
        ws.write_number(row, 7, totals["ending_credit"], money)
