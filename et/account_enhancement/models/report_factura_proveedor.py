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
    numero_factura = fields.Char('Nro. Factura', readonly=True)
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
                    -- Número de factura (name)
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
                    )::text AS numero_factura,
                    -- proveedor
                    am.partner_id AS partner_id,
                    -- moneda
                    am.currency_id AS currency_id,
                    -- Neto gravado: si hay no gravado o exento, lo ponemos en 0, si no usamos amount_untaxed
                    CASE
                        WHEN COALESCE(base_class.neto_no_gravado, 0) > 0
                        OR COALESCE(base_class.op_exentas, 0) > 0
                        THEN 0
                        ELSE am.amount_untaxed
                    END AS amount_netgrav_total,

                    -- Neto no gravado
                    COALESCE(base_class.neto_no_gravado, 0) AS amount_nograv_total,

                    -- Op. Exentas
                    COALESCE(base_class.op_exentas, 0) AS amount_op_exentas,

                    -- Otros tributos
                    COALESCE(tax_imp.otros_trib, 0) AS amount_otros_trib,

                    -- IVA total
                    COALESCE(tax_imp.iva_total, 0) AS amount_iva_total,

                    am.amount_total,
                    am.company_id
                FROM account_move am
                JOIN account_journal aj
                    ON aj.id = am.journal_id

                -- Subquery que agrupa los impuestos por factura
                LEFT JOIN (
                    SELECT
                        aml_tax.move_id,

                        -- IVA TOTAL (21, 27, 10.5, 0)
                        SUM(
                            CASE
                                WHEN at.name ILIKE 'IVA 21%%'
                                OR at.name ILIKE 'IVA 27%%'
                                OR at.name ILIKE 'IVA 10,5%%'
                                OR at.name ILIKE 'IVA 10.5%%'
                                OR at.name ILIKE 'IVA 0%%'
                                THEN ABS(aml_tax.balance)
                                ELSE 0
                            END
                        ) AS iva_total,

                        -- Otros tributos = todo lo que NO es IVA
                        SUM(
                            CASE
                                WHEN at.name ILIKE 'IVA 21%%'
                                OR at.name ILIKE 'IVA 27%%'
                                OR at.name ILIKE 'IVA 10,5%%'
                                OR at.name ILIKE 'IVA 10.5%%'
                                OR at.name ILIKE 'IVA 0%%'
                                THEN 0
                                ELSE ABS(aml_tax.balance)
                            END
                        ) AS otros_trib

                    FROM account_move_line aml_tax
                    JOIN account_tax at
                        ON at.id = aml_tax.tax_line_id          -- SOLO líneas de impuesto
                    GROUP BY aml_tax.move_id
                ) tax_imp
                    ON tax_imp.move_id = am.id
                    
                LEFT JOIN (
                    SELECT
                        aml_base.move_id,

                        -- Neto no gravado
                        SUM(
                            CASE
                                WHEN at_ex.name ILIKE 'IVA No Gravado%%'
                                THEN ABS(aml_base.balance)
                                ELSE 0
                            END
                        ) AS neto_no_gravado,

                        -- Operaciones exentas
                        SUM(
                            CASE
                                WHEN at_ex.name ILIKE 'IVA Exento%%'
                                THEN ABS(aml_base.balance)
                                ELSE 0
                            END
                        ) AS op_exentas

                    FROM account_move_line aml_base
                    JOIN account_move_line_account_tax_rel rel
                        ON rel.account_move_line_id = aml_base.id
                    JOIN account_tax at_ex
                        ON at_ex.id = rel.account_tax_id
                    GROUP BY aml_base.move_id
                ) base_class
                    ON base_class.move_id = am.id

                WHERE
                    am.state = 'posted'
                    AND am.move_type IN ('in_invoice', 'in_refund')
                    AND aj.name IN (
                        'FACTURAS PROVEEDORES LAVALLE',
                        'FACTURAS PROVEEDORES DEPOSITO'
                    )
            )
        """ % self._table)
