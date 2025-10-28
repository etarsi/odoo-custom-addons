from odoo import fields, models, tools

class ReportDebtCompositionClient(models.Model):
    _name = "report.debt.composition.client"
    _auto = False
    _description = "Composición de deuda por cliente"

    partner = fields.Many2one('res.partner', string='Cliente', readonly=True)
    fecha = fields.Date(string='Fecha', readonly=True)
    fecha_vencimiento = fields.Date(string='Fecha Vencimiento', readonly=True)
    nombre = fields.Char(string='Comprobante', readonly=True)
    comercial = fields.Many2one('res.users', string="Comercial", readonly=True)
    ejecutivo = fields.Many2one('res.users', string="Ejecutiva", readonly=True)
    importe_original = fields.Monetary(string='Importe Original', readonly=True)
    importe_residual = fields.Monetary(string='Importe Residual', readonly=True)
    importe_aplicado = fields.Monetary(string='Importe Aplicado', readonly=True)
    saldo_acumulado = fields.Monetary(string='Saldo Acumulado', readonly=True)
    origen = fields.Selection([
        ('factura', 'Factura'),
        ('nota_credito', 'Nota de Crédito'),
        ('recibo', 'Recibo')
    ], string='Origen', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)

def init(self):
    tools.drop_view_if_exists(self.env.cr, self._table)
    self.env.cr.execute(f"""
        CREATE OR REPLACE VIEW {self._table} AS (
            WITH
            -- 1) Preagrego pagos por grupo (mismo campo que usa el compute)
            pay_tot AS (
                SELECT
                    p.payment_group_id            AS pg_id,
                    COALESCE(SUM(p.l10n_ar_amount_company_currency_signed), 0.0) AS total
                FROM account_payment p
                GROUP BY p.payment_group_id
            ),
            -- 2) Link de parciales (evito OR usando UNION ALL para usar índices)
            apr_links AS (
                SELECT apr.amount, aml.move_id
                FROM account_partial_reconcile apr
                JOIN account_move_line aml ON aml.id = apr.debit_move_id
                UNION ALL
                SELECT apr.amount, aml.move_id
                FROM account_partial_reconcile apr
                JOIN account_move_line aml ON aml.id = apr.credit_move_id
            ),
            -- 3) Importe aplicado por grupo (suma de parciales de líneas de pagos)
            matched_per_pg AS (
                SELECT
                    p.payment_group_id AS pg_id,
                    COALESCE(SUM(al.amount), 0.0) AS matched
                FROM account_payment p
                JOIN apr_links al ON al.move_id = p.move_id
                GROUP BY p.payment_group_id
            ),
            -- 4) Recibos ya con totales agregados
            recibos AS (
                SELECT
                    apg.id + 2000000 AS id,
                    apg.partner_id    AS partner,
                    apg.payment_date  AS fecha,
                    NULL::date        AS fecha_vencimiento,
                    apg.name          AS nombre,
                    apg.x_comercial_id AS comercial,
                    apg.executive_id  AS ejecutivo,
                    COALESCE(pt.total, 0.0) AS importe_original,
                    (CASE WHEN apg.partner_type = 'supplier' THEN -1.0 ELSE 1.0 END)
                        * COALESCE(mp.matched, 0.0) AS importe_aplicado,
                    COALESCE(pt.total, 0.0)
                        - (CASE WHEN apg.partner_type = 'supplier' THEN -1.0 ELSE 1.0 END)
                          * COALESCE(mp.matched, 0.0) AS importe_residual,
                    'recibo'          AS origen,
                    apg.company_id,
                    apg.currency_id
                FROM account_payment_group apg
                LEFT JOIN pay_tot       pt ON pt.pg_id = apg.id
                LEFT JOIN matched_per_pg mp ON mp.pg_id = apg.id
                WHERE apg.state = 'posted'
                  AND (COALESCE(pt.total, 0.0)
                       - (CASE WHEN apg.partner_type = 'supplier' THEN -1.0 ELSE 1.0 END)
                         * COALESCE(mp.matched, 0.0)) > 0
            ),
            -- 5) Movimientos (facturas + NC) en una sola pasada
            moves AS (
                SELECT
                    CASE WHEN am.move_type = 'out_refund' THEN am.id + 1000000 ELSE am.id END AS id,
                    am.partner_id     AS partner,
                    am.invoice_date   AS fecha,
                    am.invoice_date_due AS fecha_vencimiento,
                    am.name           AS nombre,
                    am.invoice_user_id AS comercial,
                    am.executive_id   AS ejecutivo,
                    am.amount_total_signed    AS importe_original,
                    (am.amount_total_signed - am.amount_residual_signed) AS importe_aplicado,
                    am.amount_residual_signed AS importe_residual,
                    CASE WHEN am.move_type = 'out_refund' THEN 'nota_credito' ELSE 'factura' END AS origen,
                    am.company_id,
                    am.currency_id
                FROM account_move am
                WHERE am.move_type IN ('out_invoice','out_refund')
                  AND am.state = 'posted'
                  AND am.amount_residual > 0
            ),
            -- 6) Unión
            movimientos AS (
                SELECT * FROM moves
                UNION ALL
                SELECT * FROM recibos
            )
            SELECT
                id,
                partner,
                fecha,
                fecha_vencimiento,
                nombre,
                comercial,
                ejecutivo,
                importe_original,
                importe_aplicado,
                importe_residual,
                SUM(importe_residual) OVER (PARTITION BY partner ORDER BY fecha, nombre) AS saldo_acumulado,
                origen,
                company_id,
                currency_id
            FROM movimientos
        );
    """)
