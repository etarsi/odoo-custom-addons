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
        ('factura', 'Factura/ND'),
        ('recibo', 'Recibo no Imputado')
    ], string='Tipo de Comprobante')
    importe_original = fields.Monetary(string='Importe Original')
    importe_aplicado = fields.Monetary(string='Importe Aplicado')
    importe_residual = fields.Monetary(string='Importe Residual')
    company_id = fields.Many2one('res.company', string='Compañía')
    currency_id = fields.Many2one('res.currency', string='Moneda')

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW res_partner_debt_composition_report AS (

                -- FACTURAS Y NOTAS DE DÉBITO
                SELECT
                    ROW_NUMBER() OVER() AS id,
                    am.partner_id,
                    am.invoice_date AS fecha,
                    am.invoice_date_due AS vencimiento,
                    am.name AS comprobante,
                    'factura' AS tipo,
                    am.amount_total AS importe_original,
                    am.amount_total - am.amount_residual AS importe_aplicado,
                    am.amount_residual AS importe_residual,
                    am.company_id,
                    am.currency_id

                FROM account_move am
                WHERE am.move_type IN ('out_invoice', 'out_refund')
                  AND am.state = 'posted'
                  AND am.amount_residual > 0

                UNION ALL

                -- RECIBOS NO IMPUTADOS
                SELECT
                    ROW_NUMBER() OVER() + 1000000 AS id, -- evita colisión de IDs
                    apg.partner_id,
                    apg.payment_date AS fecha,
                    NULL AS vencimiento,
                    apg.name AS comprobante,
                    'recibo' AS tipo,
                    apg.amount AS importe_original,
                    apg.amount - apg.amount_residual AS importe_aplicado,
                    apg.amount_residual AS importe_residual,
                    apg.company_id,
                    apg.currency_id

                FROM account_payment_group apg
                WHERE apg.state = 'posted'
                  AND apg.amount_residual > 0
            );
        """)
