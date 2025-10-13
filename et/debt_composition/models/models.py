from odoo import fields, models, tools

class ReportDebtCompositionClient(models.Model):
    _name = "report.debt.composition.client"
    _auto = False
    _description = "Composición de deuda por cliente"

    partner_id = fields.Many2one('res.partner', string='Cliente', readonly=True)
    fecha = fields.Date(string='Fecha', readonly=True)
    fecha_vencimiento = fields.Date(string='Fecha Vencimiento', readonly=True)
    nombre = fields.Char(string='Comprobante', readonly=True)
    importe_original = fields.Monetary(string='Importe Original', readonly=True)
    importe_residual = fields.Monetary(string='Importe Residual', readonly=True)
    importe_aplicado = fields.Monetary(string='Importe Aplicado', readonly=True)
    saldo_acumulado = fields.Monetary(string='Saldo Acumulado', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True, default=lambda self: self.env.company.currency_id)
    origen = fields.Selection([
        ('factura', 'Factura / NC'),
        ('recibo', 'Recibo')
    ], string='Origen', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (

                WITH combined AS (
                    -- FACTURAS y NOTAS DE CRÉDITO (NCs restan)
                    SELECT
                        am.id AS id,
                        am.partner_id,
                        am.invoice_date AS fecha,
                        am.invoice_date_due AS fecha_vencimiento,
                        am.name AS nombre,
                        am.amount_total_signed AS importe_original,
                        CASE
                            WHEN am.move_type = 'out_refund' THEN -am.amount_residual_signed
                            ELSE am.amount_residual_signed
                        END AS importe_residual,
                        (am.amount_total_signed - am.amount_residual_signed) AS importe_aplicado,
                        am.company_id,
                        am.currency_id,
                        'factura' AS origen
                    FROM account_move am
                    WHERE am.move_type IN ('out_invoice', 'out_refund')
                    AND am.state = 'posted'
                    AND am.amount_residual_signed != 0

                    UNION ALL

                    -- RECIBOS NO IMPUTADOS (restan deuda)
                    SELECT
                        -apg.id AS id,  -- negativo para evitar conflicto con IDs de account_move
                        apg.partner_id,
                        apg.payment_date AS fecha,
                        NULL AS fecha_vencimiento,
                        apg.name AS nombre,
                        apg.x_payments_amount AS importe_original,
                        -apg.unreconciled_amount AS importe_residual,
                        COALESCE(apg.x_amount_applied, 0) AS importe_aplicado,
                        apg.company_id,
                        apg.currency_id,
                        'recibo' AS origen
                    FROM account_payment_group apg
                    WHERE apg.state = 'posted'
                    AND apg.unreconciled_amount > 0
                )

                SELECT
                    ROW_NUMBER() OVER () AS id,
                    partner_id,
                    fecha,
                    fecha_vencimiento,
                    nombre,
                    importe_original,
                    importe_residual,
                    importe_aplicado,
                    company_id,
                    currency_id,
                    origen,
                    SUM(importe_residual) OVER (
                        PARTITION BY partner_id
                        ORDER BY fecha, nombre
                    ) AS saldo_acumulado
                FROM combined
            );
        """)
