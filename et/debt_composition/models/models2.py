from odoo import fields, models, tools

class ReportDebtCompositionClient(models.Model):
    _name = "report.debt.composition.client2"
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
                WITH movimientos AS (
                    -- FACTURAS
                    SELECT
                        am.id AS id,
                        am.partner_id AS partner,
                        am.invoice_date AS fecha,
                        am.invoice_date_due AS fecha_vencimiento,
                        am.name AS nombre,
                        am.invoice_user_id AS comercial,
                        am.executive_id AS ejecutivo,
                        am.amount_total_signed AS importe_original,
                        am.amount_residual_signed AS importe_residual,
                        (am.amount_total_signed - am.amount_residual_signed) AS importe_aplicado,
                        'factura' AS origen,
                        am.company_id,
                        am.currency_id
                    FROM account_move am
                    WHERE am.move_type = 'out_invoice'
                    AND am.state = 'posted'
                    AND am.amount_residual > 0

                    UNION ALL

                    -- NOTAS DE CRÉDITO (ajuste: el aplicado debe ser positivo)
                    SELECT
                        am.id + 1000000 AS id,
                        am.partner_id AS partner,
                        am.invoice_date AS fecha,
                        am.invoice_date_due AS fecha_vencimiento,
                        am.name AS nombre,
                        am.invoice_user_id AS comercial,
                        am.executive_id AS ejecutivo,
                        am.amount_total_signed AS importe_original,
                        am.amount_residual_signed AS importe_residual,
                        ABS(am.amount_total_signed - am.amount_residual_signed) AS importe_aplicado,
                        'nota_credito' AS origen,
                        am.company_id,
                        am.currency_id
                    FROM account_move am
                    WHERE am.move_type = 'out_refund'
                    AND am.state = 'posted'
                    AND am.amount_residual > 0

                    UNION ALL

                    -- RECIBOS
                    SELECT
                        apg.id + 2000000 AS id,
                        apg.partner_id AS partner,
                        apg.payment_date AS fecha,
                        NULL AS fecha_vencimiento,
                        apg.name AS nombre,
                        apg.x_comercial_id AS comercial,
                        apg.executive_id AS ejecutivo,
                        -COALESCE((
                            SELECT SUM(ap.amount)
                            FROM account_payment ap
                            WHERE ap.payment_group_id = apg.id
                        ), 0.0) AS importe_original,
                        -COALESCE((
                            SELECT SUM(pr.amount)
                            FROM account_payment ap
                            JOIN account_move_line aml ON aml.payment_id = ap.id
                            JOIN account_partial_reconcile pr ON pr.debit_move_id = aml.id OR pr.credit_move_id = aml.id
                            WHERE ap.payment_group_id = apg.id
                        ), 0.0) AS importe_aplicado,
                        COALESCE((
                            SELECT SUM(ap.amount)
                            FROM account_payment ap
                            WHERE ap.payment_group_id = apg.id
                        ), 0.0) - COALESCE((
                            SELECT SUM(pr.amount)
                            FROM account_payment ap
                            JOIN account_move_line aml ON aml.payment_id = ap.id
                            JOIN account_partial_reconcile pr ON pr.debit_move_id = aml.id OR pr.credit_move_id = aml.id
                            WHERE ap.payment_group_id = apg.id
                        ), 0.0) AS importe_residual,
                        'recibo' AS origen,
                        apg.company_id,
                        apg.currency_id
                    FROM account_payment_group apg
                    WHERE apg.state = 'posted'



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
