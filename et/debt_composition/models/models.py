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
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True, default=lambda self: self.env.company.currency_id)
    origen = fields.Selection([
        ('factura', 'Factura / NC'),
        ('recibo', 'Recibo')
    ], string='Origen', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(f"""
            CREATE OR REPLACE VIEW report_movimientos_clientes AS (
                -- FACTURAS Y NOTAS DE CRÉDITO
                SELECT
                    am.id AS id,
                    am.partner_id,
                    am.invoice_date AS fecha,
                    am.invoice_date_due AS fecha_vencimiento,
                    am.name AS nombre,
                    am.amount_total_signed AS importe_original,
                    am.amount_residual_signed AS importe_residual,
                    NULL::numeric AS importe_aplicado,
                    am.company_id,
                    'factura' AS origen
                FROM account_move am
                WHERE am.move_type IN ('out_invoice', 'out_refund')
                AND am.state = 'posted'

                UNION ALL

                -- RECIBOS (account_payment_group)
                SELECT
                    -apg.id AS id,  -- negativo para que no choquen con los IDs de account_move
                    apg.partner_id,
                    apg.payment_date AS fecha,
                    NULL AS fecha_vencimiento,
                    apg.name AS nombre,
                    apg.x_payments_amount AS importe_original,
                    'recibo' AS origen
                FROM account_payment_group apg
                WHERE apg.state IN ('posted', 'reconciled')
            );


        """)
