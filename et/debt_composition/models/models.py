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
    cr = self.env.cr
    # 0) Índices clave (si aún no existen)
    cr.execute("""
        CREATE INDEX IF NOT EXISTS idx_am_sales_open
        ON account_move (partner_id, invoice_date, id)
        WHERE move_type IN ('out_invoice','out_refund') AND state='posted' AND amount_residual > 0;

        CREATE INDEX IF NOT EXISTS idx_apg_posted_unrec
        ON account_payment_group (partner_id, payment_date, company_id)
        WHERE state='posted' AND unreconciled_amount > 0;

        CREATE INDEX IF NOT EXISTS idx_payment_pg_state
        ON account_payment (payment_group_id, state);

        CREATE INDEX IF NOT EXISTS idx_apr_debit  ON account_partial_reconcile (debit_move_id);
        CREATE INDEX IF NOT EXISTS idx_apr_credit ON account_partial_reconcile (credit_move_id);
        CREATE INDEX IF NOT EXISTS idx_aml_move   ON account_move_line (move_id);
    """)

    # 1) Materialized views (preagregados)
    cr.execute("""
        -- Totales de pagos por grupo (company currency + signo aplicado)
        CREATE MATERIALIZED VIEW IF NOT EXISTS apg_pay_tot_mv AS
        SELECT
            p.payment_group_id AS pg_id,
            COALESCE(SUM(p.l10n_ar_amount_company_currency_signed), 0.0) AS total
        FROM account_payment p
        WHERE p.state IN ('posted','reconciled')
        GROUP BY p.payment_group_id
        WITH NO DATA;
        CREATE UNIQUE INDEX IF NOT EXISTS apg_pay_tot_mv_pk ON apg_pay_tot_mv(pg_id);

        -- Aplicado por grupo (suma de parciales sobre líneas del pago)
        CREATE MATERIALIZED VIEW IF NOT EXISTS apg_matched_per_pg_mv AS
        SELECT
            p.payment_group_id AS pg_id,
            COALESCE(SUM(al.amount), 0.0) AS matched
        FROM account_payment p
        JOIN (
            SELECT apr.amount, aml.move_id
            FROM account_partial_reconcile apr
            JOIN account_move_line aml ON aml.id = apr.debit_move_id
            UNION ALL
            SELECT apr.amount, aml.move_id
            FROM account_partial_reconcile apr
            JOIN account_move_line aml ON aml.id = apr.credit_move_id
        ) al ON al.move_id = p.move_id
        GROUP BY p.payment_group_id
        WITH NO DATA;
        CREATE UNIQUE INDEX IF NOT EXISTS apg_matched_per_pg_mv_pk ON apg_matched_per_pg_mv(pg_id);
    """)

    # 2) Primer REFRESH (sin CONCURRENTLY: init corre dentro de una transacción)
    cr.execute("REFRESH MATERIALIZED VIEW apg_pay_tot_mv;")
    cr.execute("REFRESH MATERIALIZED VIEW apg_matched_per_pg_mv;")

    # 3) Vista principal (misma forma/columnas que la tuya, solo cambia la fuente de pt/mp)
    tools.drop_view_if_exists(cr, self._table)
    cr.execute(f"""
    CREATE OR REPLACE VIEW {self._table} AS
      SELECT
        id, partner, fecha, fecha_vencimiento, nombre,
        comercial, ejecutivo,
        importe_original, importe_aplicado, importe_residual,
        SUM(importe_residual) OVER (PARTITION BY partner ORDER BY fecha, nombre) AS saldo_acumulado,
        origen, company_id, currency_id
      FROM (
        -- FACT/NC
        SELECT
          CASE WHEN am.move_type = 'out_refund' THEN am.id + 1000000 ELSE am.id END AS id,
          am.partner_id       AS partner,
          am.invoice_date     AS fecha,
          am.invoice_date_due AS fecha_vencimiento,
          am.name             AS nombre,
          am.invoice_user_id  AS comercial,
          am.executive_id     AS ejecutivo,
          am.amount_total_signed                         AS importe_original,
          (am.amount_total_signed - am.amount_residual_signed) AS importe_aplicado,
          am.amount_residual_signed                      AS importe_residual,
          CASE WHEN am.move_type = 'out_refund' THEN 'nota_credito' ELSE 'factura' END AS origen,
          am.company_id,
          am.currency_id
        FROM account_move am
        WHERE am.move_type IN ('out_invoice','out_refund')
          AND am.state = 'posted'
          AND am.amount_residual > 0

        UNION ALL

        -- RECIBOS usando las MVs preagregadas
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
          'recibo' AS origen,
          apg.company_id,
          apg.currency_id
        FROM account_payment_group apg
        LEFT JOIN apg_pay_tot_mv       pt ON pt.pg_id = apg.id
        LEFT JOIN apg_matched_per_pg_mv mp ON mp.pg_id = apg.id
        WHERE apg.state = 'posted'
          AND (COALESCE(pt.total, 0.0)
               - (CASE WHEN apg.partner_type = 'supplier' THEN -1.0 ELSE 1.0 END)
                 * COALESCE(mp.matched, 0.0)) > 0
      ) movimientos;
    """)