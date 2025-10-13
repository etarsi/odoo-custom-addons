from odoo import models, fields, api
from odoo.osv import expression

class ResPartnerDebtCompositionReport(models.Model):
    _name = 'res.partner.debt.composition.report'
    _description = 'Composición de Deudas de Clientes'
    _auto = False
    _order = 'partner_id, fecha'
    _rec_name = 'partner_name'

    partner_name = fields.Char(string='Nombre del Cliente', store=True)
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


    @api.model
    def _name_search(self, name='', args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        if name:
            args = expression.OR([args, [('partner_name', operator, name)]])
        return self._search(args, limit=limit, access_rights_uid=name_get_uid)


    def init(self):
        self.env.cr.execute("""
            DROP VIEW IF EXISTS res_partner_debt_composition_report CASCADE;
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
                            WHEN am.move_type = 'out_refund' THEN -am.amount_residual  -- NC restan
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
                        -apg.unreconciled_amount AS importe_residual,  -- signo negativo
                        apg.company_id,
                        apg.currency_id
                    FROM account_payment_group apg
                    WHERE apg.state = 'posted'
                    AND apg.unreconciled_amount > 0
                )

                SELECT
                    ROW_NUMBER() OVER() AS id,
                    c.partner_id,
                    rp.name AS partner_name,
                    c.fecha,
                    c.vencimiento,
                    c.comprobante,
                    c.tipo,
                    c.importe_original,
                    c.importe_aplicado,
                c.importe_residual,
                SUM(c.importe_residual)
                    OVER (PARTITION BY c.partner_id ORDER BY c.fecha, c.comprobante)
                    AS saldo_acumulado,
                c.company_id,
                c.currency_id
            FROM combined c
            JOIN res_partner rp ON rp.id = c.partner_id
        );
    """)


