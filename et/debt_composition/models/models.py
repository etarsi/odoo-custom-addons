from odoo import fields, models, tools
class ReportDebtCompositionClient(models.Model):
    _name = "report.debt.composition.client"
    _auto = False
    _description = "Composición de deuda por cliente"

    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)

    fecha = fields.Date(string='Fecha')
    fecha_vencimiento = fields.Date(string='Fecha Vencimiento')
    nombre = fields.Char(string='Comprobante')
    importe_original = fields.Monetary(string='Importe Original')
    importe_aplicado = fields.Monetary(string='Importe Aplicado')
    importe_residual = fields.Monetary(string='Importe Residual')
    saldo_acumulado = fields.Monetary(string='Saldo Acumulado')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    company_id = fields.Many2one('res.company', string='Compañía')
    origen = fields.Selection([('factura', 'Factura'), ('recibo', 'Recibo')], string='Origen')


    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW report_debt_composition_client AS (

                WITH combined AS (
                    -- FACTURAS y NC
                    SELECT
                        am.id AS id,
                        am.partner_id,
                        am.invoice_date AS fecha,
                        am.invoice_date_due AS fecha_vencimiento,
                        am.name AS nombre,
                        am.amount_total_signed AS importe_original,
                        am.amount_total_signed - am.amount_residual_signed AS importe_aplicado,
                        CASE
                            WHEN am.move_type = 'out_refund' THEN -am.amount_residual_signed
                            ELSE am.amount_residual_signed
                        END AS importe_residual,
                        am.company_id,
                        am.currency_id,
                        'factura' AS origen
                    FROM account_move am
                    WHERE am.move_type IN ('out_invoice', 'out_refund')
                    AND am.state = 'posted'
                    AND am.amount_residual_signed != 0

                    UNION ALL

                    -- RECIBOS
                    SELECT
                        -apg.id AS id,
                        apg.partner_id,
                        apg.payment_date AS fecha,
                        NULL AS fecha_vencimiento,
                        apg.name AS nombre,
                        apg.x_payments_amount AS importe_original,
                        COALESCE(apg.x_amount_applied, 0) AS importe_aplicado,
                        -apg.unreconciled_amount AS importe_residual,
                        apg.company_id,
                        apg.currency_id,
                        'recibo' AS origen
                    FROM account_payment_group apg
                    WHERE apg.state IN ('posted', 'reconciled')
                    AND apg.unreconciled_amount != 0
                )

                SELECT
                    row_number() OVER () AS id,
                    partner_id,
                    fecha,
                    fecha_vencimiento,
                    nombre,
                    importe_original,
                    importe_aplicado,
                    importe_residual,
                    SUM(importe_residual) OVER (
                        PARTITION BY partner_id
                        ORDER BY fecha, nombre
                    ) AS saldo_acumulado,
                    company_id,
                    currency_id,
                    origen
                FROM combined
            );
        """)
