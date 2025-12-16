# models/report_customer_rubro.py
from odoo import models, fields, tools


class ReportFacturaProveedor(models.Model):
    _name = 'report.factura.proveedor'
    _description = 'Reporte de Facturas Proveedor'
    _auto = False
    _order = 'fecha asc, partner_id asc, id asc'

    

    fecha = fields.Date('Fecha', readonly=True)
    tipo = fields.Many2one('l10n_latam.document.type', 'Tipo', readonly=True)
    punto_venta = fields.Char('Punto de Venta', readonly=True)
    numero_desde = fields.Char('Número Desde', readonly=True)
    numero_hasta = fields.Char('Número Hasta', readonly=True)
    partner_id = fields.Many2one('res.partner', 'Denominación Emisor', readonly=True)
    currency_id = fields.Many2one('res.currency', 'Moneda', readonly=True)
    amount_netgrav_total = fields.Monetary('Neto Gravado Total', readonly=True, currency_field='currency_id')
    amount_nograv_total = fields.Monetary('Neto No Gravado', readonly=True, currency_field='currency_id')
    amount_op_exentas = fields.Monetary('Op. Exentas', readonly=True, currency_field='currency_id')
    amount_otros_trib = fields.Monetary('Otros Tributos', readonly=True, currency_field='currency_id')
    amount_iva_total = fields.Monetary('IVA Total', readonly=True, currency_field='currency_id')
    amount_total = fields.Monetary('Importe Total', readonly=True, currency_field='currency_id')
    company_id = fields.Many2one('res.company', 'Compañía', readonly=True)



    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    am.id AS id,
                    am.invoice_date AS fecha,
                    am.l10n_latam_document_type_id AS tipo,

                    -- Tomamos número de comprobante (name)
                    CAST(
                        NULLIF(
                            split_part(
                                regexp_replace(
                                    COALESCE(am.name),
                                    '^[^0-9]*',
                                    ''
                                ),
                                '-',
                                1
                            ),
                            ''
                        ) AS INTEGER
                    )::text AS punto_venta,

                    -- Número de comprobante (name)
                    CAST(
                        NULLIF(
                            split_part(
                                regexp_replace(
                                    COALESCE(am.name),
                                    '^[^0-9]*',
                                    ''
                                ),
                                '-',
                                2
                            ),
                            ''
                        ) AS INTEGER
                    )::text AS numero_desde,

                    -- Número de comprobante (name)
                    CAST(
                        NULLIF(
                            split_part(
                                regexp_replace(
                                    COALESCE(am.name),
                                    '^[^0-9]*',
                                    ''
                                ),
                                '-',
                                2
                            ),
                            ''
                        ) AS INTEGER
                    )::text AS numero_hasta,
                    -- proveedor
                    am.partner_id AS partner_id,
                    -- moneda
                    am.currency_id AS currency_id,
                    -- monto neto gravado total
                    (CASE
                        WHEN tax.iva_no_gravado > 0.0 OR tax.otros_trib > 0.0 THEN 0.0
                        ELSE am.amount_untaxed
                    END) AS amount_netgrav_total,
                    -- Monto no gravado 
                    tax.iva_no_gravado AS amount_nograv_total,
                    -- Op. Exentas
                    tax.iva_exento AS amount_op_exentas,
                    -- Otros tributos = todas las percepciones/impuestos que NO sean IVA 21
                    tax.otros_trib AS amount_otros_trib,
                    -- IVA total
                    tax.iva_total AS amount_iva_total,
                    -- Importe total
                    am.amount_total AS amount_total,
                    -- Company
                    am.company_id AS company_id
                FROM account_move am
                JOIN account_journal aj
                    ON aj.id = am.journal_id

                -- Subquery que agrupa los impuestos por factura
                LEFT JOIN (
                    SELECT
                        aml.move_id,
                        -- IVA No Gravado
                        SUM(
                            CASE
                                -- TODOS QUE SON IVA No Gravado
                                WHEN at.name ILIKE 'IVA No Gravado%%'
                                    THEN ABS(aml.balance)
                                ELSE 0
                            END
                        ) as iva_no_gravado,
                        
                        -- IVA Exento
                        SUM(
                            CASE
                                -- todo lo que NO es IVA 21 se va a otros tributos
                                WHEN at.name ILIKE 'IVA Exento%%'
                                    THEN ABS(aml.balance)
                                ELSE 0
                            END
                        ) AS iva_exento,    

                        -- otros tributos
                        SUM(
                            CASE
                                -- aca matcheamos el IVA exento
                                WHEN at.name NOT IN ('IVA 21%%', 'IVA 27%%', 'IVA 10.5%%', 'IVA 0%%', 'IVA Exento%%', 'IVA No Gravado%%')
                                    THEN ABS(aml.balance)
                                ELSE 0
                            END
                        ) AS otros_trib,
                        
                        -- IVA TOTAL
                        SUM(
                            CASE
                                WHEN at.name IN ('IVA 21%%', 'IVA 27%%', 'IVA 10.5%%', 'IVA 0%%')
                                    THEN ABS(aml.balance)
                                ELSE 0
                            END
                        ) AS iva_total            
                    FROM account_move_line aml
                    JOIN account_tax at
                        ON at.id = aml.tax_line_id
                    GROUP BY aml.move_id
                ) AS tax
                    ON tax.move_id = am.id

                WHERE
                    am.state = 'posted'
                    AND am.move_type IN ('in_invoice', 'in_refund')
                    AND aj.name IN (
                        'FACTURAS PROVEEDORES LAVALLE',
                        'FACTURAS PROVEEDORES DEPOSITO'
                    )
            )
        """ % self._table)
