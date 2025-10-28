from odoo import models, fields


class ResPartnerDebtCompositionReport(models.Model):
    _name = 'res.partner.debt.composition.report'
    _description = 'Composición de Deuda por Cliente'
    _auto = False
    _order = 'fecha desc, comprobante'

    # Campos requeridos por el ORM
    create_date = fields.Datetime(readonly=True)
    write_date = fields.Datetime(readonly=True)
    create_uid = fields.Many2one('res.users', readonly=True)
    write_uid = fields.Many2one('res.users', readonly=True)

    x_partner_id = fields.Integer(string='ID Cliente')
    partner_id = fields.Char(string='Cliente')  # Aquí va el nombre
    fecha = fields.Date(string='Fecha')
    vencimiento = fields.Date(string='Vencimiento')
    comprobante = fields.Char(string='Comprobante')
    tipo = fields.Selection([
        ('factura', 'Factura'),
        ('nota_credito', 'Nota de Crédito'),
        ('recibo', 'Recibo'),
        ('otros', 'Otros'),
    ], string='Tipo')
    importe_original = fields.Float(string='Importe Original')
    importe_aplicado = fields.Float(string='Importe Aplicado')
    importe_residual = fields.Monetary(string='Importe Pendiente')
    saldo_acumulado = fields.Monetary(string='Saldo Acumulado')
    company_id = fields.Many2one('res.company', string='Compañía')
    currency_id = fields.Many2one('res.currency', string='Moneda')

    def init(self):
        self.env.cr.execute("""
            DROP VIEW IF EXISTS res_partner_debt_composition_report CASCADE;
            CREATE VIEW res_partner_debt_composition_report AS (

                WITH combined AS (
                    SELECT
                        am.partner_id AS x_partner_id,
                        rp.name AS partner_id,
                        am.invoice_date AS fecha,
                        am.invoice_date_due AS vencimiento,
                        am.name AS comprobante,
                        CASE
                            WHEN am.move_type = 'out_invoice' THEN 'factura'
                            WHEN am.move_type = 'out_refund' THEN 'nota_credito'
                            ELSE 'otros'
                        END AS tipo,
                        am.amount_total AS importe_original,
                        (am.amount_total - am.amount_residual) AS importe_aplicado,
                        CASE
                            WHEN am.move_type = 'out_refund' THEN -am.amount_residual
                            ELSE am.amount_residual
                        END AS importe_residual,
                        am.company_id,
                        am.currency_id
                    FROM account_move am
                    JOIN res_partner rp ON rp.id = am.partner_id
                    WHERE am.move_type IN ('out_invoice', 'out_refund')
                    AND am.state = 'posted'
                    AND am.amount_residual > 0

                    UNION ALL

                    SELECT
                        apg.partner_id AS x_partner_id,
                        rp.name AS partner_id,
                        apg.payment_date AS fecha,
                        NULL AS vencimiento,
                        apg.name AS comprobante,
                        'recibo' AS tipo,
                        (
                            SELECT COALESCE(SUM(p.l10n_ar_amount_company_currency_signed), 0.0)
                            FROM account_payment p
                            WHERE p.payment_group_id = apg.id
                        ) AS importe_original,
                        COALESCE(apg.x_amount_applied, 0) AS importe_aplicado,
                        -apg.unreconciled_amount AS importe_residual,
                        apg.company_id,
                        apg.currency_id
                    FROM account_payment_group apg
                    JOIN res_partner rp ON rp.id = apg.partner_id
                    WHERE apg.state = 'posted'
                    AND apg.unreconciled_amount > 0
                )

                SELECT
                    ROW_NUMBER() OVER() AS id,
                    NULL::timestamp AS create_date,
                    NULL::integer AS create_uid,
                    NULL::timestamp AS write_date,
                    NULL::integer AS write_uid,
                    x_partner_id,
                    partner_id,
                    fecha,
                    vencimiento,
                    comprobante,
                    tipo,
                    importe_original,
                    importe_aplicado,
                    importe_residual,
                    SUM(importe_residual) OVER (PARTITION BY x_partner_id ORDER BY fecha, comprobante) AS saldo_acumulado,
                    company_id,
                    currency_id
                FROM combined
            );
        """)
