# models/report_customer_rubro.py
from odoo import models, fields, tools

class ReportCustomerCommercialRubro(models.Model):
    _name = 'report.customer.comercial.rubro'
    _description = 'Facturación por cliente / comercial y rubro'
    _auto = False
    _order = 'date desc, partner_id'

    date = fields.Date('Fecha', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Cliente', readonly=True)
    comercial_id = fields.Many2one('res.users', 'Comercial', readonly=True)
    rubro_id = fields.Many2one(
        'product.category',
        string='Rubro (padre)',
        readonly=True,
    )
    amount = fields.Monetary('Importe', readonly=True)
    company_id = fields.Many2one('res.company', 'Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Moneda', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    am.company_id,
                    am.invoice_date AS date,
                    am.partner_id,
                    am.invoice_user_id AS comercial_id,
                    parent_categ.id AS rubro_id,
                    am.currency_id AS currency_id,
                    SUM(
                        CASE
                            -- Si es NC, damos vuelta el signo
                            WHEN am.move_type = 'out_refund'
                                THEN -aml.price_subtotal
                            ELSE aml.price_subtotal
                        END
                    ) AS amount
                FROM account_move_line aml
                JOIN account_move am
                    ON aml.move_id = am.id
                LEFT JOIN product_product pp
                    ON aml.product_id = pp.id
                LEFT JOIN product_template pt
                    ON pp.product_tmpl_id = pt.id
                LEFT JOIN product_category c
                    ON pt.categ_id = c.id
                -- Rubro = categoría padre si existe, si no, la propia
                LEFT JOIN product_category parent_categ
                    ON parent_categ.id = COALESCE(c.parent_id, c.id)
                WHERE
                    am.state = 'posted'
                    AND am.move_type IN ('out_invoice', 'out_refund')
                    AND aml.display_type IS NULL   -- sin notas/secciones
                GROUP BY
                    am.company_id,
                    am.invoice_date,
                    am.partner_id,
                    am.invoice_user_id,
                    parent_categ.id,
                    am.currency_id
            )
        """ % self._table)
