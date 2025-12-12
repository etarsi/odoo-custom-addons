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
                    am.partner_id AS partner_id,
                    am.currency_id AS currency_id,
                    -- Definimos un signo para que las NC de proveedor resten
                    (am.amount_untaxed * 
                        CASE
                            WHEN am.move_type = 'in_refund' THEN -1
                            ELSE 1
                        END
                    ) AS amount_netgrav_total,

                    -- Por ahora estos en 0 (luego se pueden desglosar por impuestos)
                    0.0::numeric AS amount_nograv_total,
                    0.0::numeric AS amount_op_exentas,
                    0.0::numeric AS amount_otros_trib,

                    (am.amount_tax *
                        CASE
                            WHEN am.move_type = 'in_refund' THEN -1
                            ELSE 1
                        END
                    ) AS amount_iva_total,

                    (am.amount_total *
                        CASE
                            WHEN am.move_type = 'in_refund' THEN -1
                            ELSE 1
                        END
                    ) AS amount_total

                FROM account_move am
                JOIN account_journal aj
                    ON aj.id = am.journal_id
                WHERE
                    am.state = 'posted'
                    AND am.move_type IN ('in_invoice', 'in_refund')
                    AND aj.name IN (
                        'FACTURAS PROVEEDORES LAVALLE',
                        'FACTURAS PROVEEDORES DEPOSITO'
                    )
            )
        """ % self._table)
