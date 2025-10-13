from odoo import models, fields

class ResPartnerDebtCompositionReport(models.Model):
    _name = 'res.partner.debt.composition.report'
    _description = 'Composición de Deudas de Clientes'
    _auto = False
    _order = 'partner_id, fecha'

    partner_id = fields.Many2one('res.partner', string='Cliente')
    fecha = fields.Date(string='Fecha del Comprobante')
    vencimiento = fields.Date(string='Fecha de Vencimiento')
    comprobante = fields.Char(string='Comprobante')
    tipo = fields.Selection([
        ('factura', 'Factura / ND'),
        ('recibo', 'Recibo no Imputado')
    ], string='Tipo')
    importe_original = fields.Monetary(string='Importe Original')
    importe_aplicado = fields.Monetary(string='Importe Aplicado')
    importe_residual = fields.Monetary(string='Importe Residual')
    saldo_acumulado = fields.Monetary(string='Saldo Acumulado')
    company_id = fields.Many2one('res.company', string='Compañía')
    currency_id = fields.Many2one('res.currency', string='Moneda')

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW res_partner_debt_composition_report AS (

                WITH combined AS (
                    -- FACTURAS / ND / NC
                    SELECT
                        am.partner_id,
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
                            WHEN am.move_type = 'out_refund' THEN -am.amount_residual  -- 🔹 NC restan
                            ELSE am.amount_residual
                        END AS importe_residual,
                        am.company_id,
                        am.currency_id
                    FROM account_move am
                    WHERE am.move_type IN ('out_invoice', 'out_refund')
                    AND am.state = 'posted'
                    AND am.amount_residual > 0

                    UNION ALL

                    -- RECIBOS NO IMPUTADOS (restan deuda)
                    SELECT
                        apg.partner_id,
                        apg.payment_date AS fecha,
                        NULL AS vencimiento,
                        apg.name AS comprobante,
                        'recibo' AS tipo,
                        apg.x_payments_amount AS importe_original,
                        COALESCE(apg.x_amount_applied, 0) AS importe_aplicado,
                        -apg.unreconciled_amount AS importe_residual,  -- 🔹 signo negativo
                        apg.company_id,
                        apg.currency_id
                    FROM account_payment_group apg
                    WHERE apg.state = 'posted'
                    AND apg.unreconciled_amount > 0
                )

                SELECT
                    ROW_NUMBER() OVER() AS id,
                    partner_id,
                    fecha,
                    vencimiento,
                    comprobante,
                    tipo,
                    importe_original,
                    importe_aplicado,
                    importe_residual,
                    SUM(importe_residual)
                        OVER (PARTITION BY partner_id ORDER BY fecha, comprobante)
                        AS saldo_acumulado,
                    company_id,
                    currency_id
                FROM combined
            );
        """)

