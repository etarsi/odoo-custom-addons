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
                WITH movimientos AS (
                    -- FACTURAS Y NC
                    SELECT
                        am.id AS id,
                        rp.id AS partner_id,
                        am.invoice_date AS fecha,
                        am.invoice_date_due AS fecha_vencimiento,
                        am.name AS nombre,
                        am.amount_total_signed AS importe_original,
                        am.amount_residual_signed AS importe_residual,
                        (am.amount_total_signed - am.amount_residual_signed) AS importe_aplicado,
                        am.company_id,
                        am.currency_id,
                        'factura' AS origen
                    FROM account_move am
                    JOIN res_partner rp ON rp.id = am.partner_id
                    WHERE am.move_type IN ('out_invoice', 'out_refund')
                    AND am.state = 'posted'

                    UNION ALL

                    -- RECIBOS
                    SELECT
                        -apg.id AS id,
                        rp.id AS partner_id,
                        apg.payment_date AS fecha,
                        NULL AS fecha_vencimiento,
                        apg.name AS nombre,
                        apg.x_payments_amount AS importe_original,
                        -apg.unreconciled_amount AS importe_residual,
                        apg.x_amount_applied AS importe_aplicado,
                        apg.company_id,
                        apg.currency_id,
                        'recibo' AS origen
                    FROM account_payment_group apg
                    JOIN res_partner rp ON rp.id = apg.partner_id
                    WHERE apg.state IN ('posted', 'reconciled')
                )

                SELECT
                    ROW_NUMBER() OVER () AS id,
                    m.partner_id,
                    m.fecha,
                    m.fecha_vencimiento,
                    m.nombre,
                    m.importe_original,
                    m.importe_residual,
                    m.importe_aplicado,
                    m.company_id,
                    m.currency_id,
                    m.origen,
                    SUM(m.importe_residual) OVER (
                        PARTITION BY m.partner_id
                        ORDER BY m.fecha, m.nombre
                    ) AS saldo_acumulado
                FROM movimientos m
            );
        """)
