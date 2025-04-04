from odoo import fields, models, tools

class ReportDebtCompositionClient(models.Model):
    _name = "report.debt.composition.client"
    _auto = False
    _description = "Composición de deuda por cliente"

    partner_id = fields.Many2one('res.partner', string="Cliente")
    invoice_date = fields.Date(string="Fecha Comprobante")
    invoice_date_due = fields.Date(string="Fecha Vencimiento")
    name = fields.Char(string="Comprobante")
    amount_total_signed = fields.Monetary(string="Importe Original")
    amount_residual_signed = fields.Monetary(string="Importe Residual")
    x_amount_paid = fields.Monetary(string="Importe Aplicado")
    x_accumulated_balance_client = fields.Monetary(string="Saldo Acumulado")
    company_id = fields.Many2one('res.company', string="Compañía")
    currency_id = fields.Many2one('res.currency', string="Moneda")

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(f"""
            CREATE OR REPLACE VIEW report_composicion_deuda_cliente AS (
                SELECT
                    row_number() OVER () AS id,
                    am.partner_id,
                    am.invoice_date,
                    am.invoice_date_due,
                    am.name,
                    am.company_id,
                    'factura' AS document_type,
                    am.amount_total_signed AS amount_total_signed,
                    COALESCE(applied.total_applied, 0) AS x_amount_paid,
                    am.amount_residual_signed AS amount_residual_signed,
                    (am.amount_total_signed - COALESCE(applied.total_applied, 0)) AS x_accumulated_balance_client
                FROM account_move am
                LEFT JOIN (
                    SELECT
                        aml.move_id,
                        SUM(ABS(apr.amount)) AS total_applied
                    FROM account_partial_reconcile apr
                    JOIN account_move_line aml ON apr.debit_move_id = aml.id OR apr.credit_move_id = aml.id
                    GROUP BY aml.move_id
                ) applied ON applied.move_id = am.id
                WHERE am.move_type IN ('out_invoice', 'out_refund')
                AND am.state = 'posted'
                AND am.amount_residual_signed != 0

                UNION ALL

                SELECT
                    row_number() OVER () + 1000000 AS id,
                    am.partner_id,
                    am.date AS invoice_date,
                    NULL AS invoice_date_due,
                    am.name,
                    am.company_id,
                    'recibo' AS document_type,
                    am.amount_total_signed AS amount_total_signed,
                    COALESCE(applied.total_applied, 0) AS x_amount_paid,
                    am.amount_residual_signed AS amount_residual_signed,
                    (am.amount_total_signed - COALESCE(applied.total_applied, 0)) AS x_accumulated_balance_client
                FROM account_move am
                JOIN account_move_line aml ON aml.move_id = am.id
                LEFT JOIN (
                    SELECT
                        aml.move_id,
                        SUM(ABS(apr.amount)) AS total_applied
                    FROM account_partial_reconcile apr
                    JOIN account_move_line aml ON apr.debit_move_id = aml.id OR apr.credit_move_id = aml.id
                    GROUP BY aml.move_id
                ) applied ON applied.move_id = am.id
                WHERE am.move_type = 'entry'
                AND aml.account_internal_type = 'receivable'
                AND am.state = 'posted'
                AND am.amount_residual_signed != 0
            );

        """)
