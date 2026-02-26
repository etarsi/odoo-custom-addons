# models/report_customer_rubro.py
from odoo import models, fields, tools


class ReportFacturaRubrosTempDc(models.Model):
    _name = 'report.factura.rubros.temp.dc'
    _description = 'Reporte de Facturas por Rubros Temporada Día del Niño 2026'
    _auto = False
    _order = 'id asc, partner_id asc, comercial_id asc'
    
    partner_id = fields.Many2one('res.partner', 'Cliente', readonly=True)
    comercial_id = fields.Many2one('res.users', 'Comercial', readonly=True)
    amount_juguetes = fields.Monetary('Juguetes', readonly=True, currency_field='currency_id') 
    amount_maquillaje = fields.Monetary('Maquillaje', readonly=True, currency_field='currency_id')
    amount_rodados = fields.Monetary('Rodados', readonly=True, currency_field='currency_id')
    amount_pelotas = fields.Monetary('Pelotas', readonly=True, currency_field='currency_id')
    amount_inflables = fields.Monetary('Inflables', readonly=True, currency_field='currency_id')
    amount_pst_agua = fields.Monetary('Pistolas de Agua', readonly=True, currency_field='currency_id')
    amount_vehiculos_b = fields.Monetary('Vehículos a Batería', readonly=True, currency_field='currency_id')
    amount_rodados_inf = fields.Monetary('Rodados Infantiles', readonly=True, currency_field='currency_id')
    amount_caballitos_slt = fields.Monetary('Caballitos Saltarines', readonly=True, currency_field='currency_id')
    amount_otros = fields.Monetary('Otros Rubros', readonly=True, currency_field='currency_id')
    total_amount_rubro = fields.Monetary('Total', readonly=True, currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', 'Moneda', readonly=True)



    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    am.partner_id,
                    am.invoice_user_id AS comercial_id,
                    am.currency_id AS currency_id,

                    -- JUGUETES
                    SUM(
                        CASE
                            WHEN TRIM(UPPER(parent_categ.name)) = 'JUGUETES'
                            THEN (aml.price_total * 
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS amount_juguetes,

                    -- MAQUILLAJE
                    SUM(
                        CASE
                            WHEN TRIM(UPPER(parent_categ.name)) = 'MAQUILLAJE'
                            THEN (aml.price_total * 
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS amount_maquillaje,

                    -- RODADOS
                    SUM(
                        CASE
                            WHEN TRIM(UPPER(parent_categ.name)) = 'RODADOS'
                            THEN (aml.price_total * 
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS amount_rodados,

                    -- PELOTAS
                    SUM(
                        CASE
                            WHEN TRIM(UPPER(parent_categ.name)) = 'PELOTAS'
                            THEN (aml.price_total *
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS amount_pelotas,

                    -- INFLABLES
                    SUM(
                        CASE
                            WHEN TRIM(UPPER(parent_categ.name)) = 'INFLABLES'
                            THEN (aml.price_total *
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS amount_inflables,

                    -- PISTOLAS DE AGUA
                    SUM(
                        CASE
                            WHEN TRIM(UPPER(parent_categ.name)) = 'PISTOLAS DE AGUA'
                            THEN (aml.price_total *
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS amount_pst_agua,

                    -- VEHICULOS A BATERIA
                    SUM(
                        CASE
                            WHEN TRIM(UPPER(parent_categ.name)) = 'VEHICULOS A BATERIA'
                            THEN (aml.price_total *
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS amount_vehiculos_b,

                    -- RODADOS INFANTILES
                    SUM(
                        CASE
                            WHEN TRIM(UPPER(parent_categ.name)) = 'RODADOS INFANTILES'
                            THEN (aml.price_total *
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS amount_rodados_inf,
                    
                    -- CABALLITOS SALTARINES
                    SUM(
                        CASE
                            WHEN TRIM(UPPER(parent_categ.name)) = 'CABALLITOS SALTARINES'
                            THEN (aml.price_total *
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS amount_caballitos_slt,
                    
                    -- OTROS RUBROS (los que no están en la lista)
                    SUM(
                        CASE
                            WHEN parent_categ.id IS NOT null AND TRIM(UPPER(parent_categ.name)) NOT IN (
                                'JUGUETES',
                                'MAQUILLAJE',
                                'RODADOS',
                                'PELOTAS',
                                'INFLABLES',
                                'PISTOLAS DE AGUA',
                                'VEHICULOS A BATERIA',
                                'RODADOS INFANTILES',
                                'CABALLITOS SALTARINES'
                            )
                            THEN (aml.price_total *
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS amount_otros,

                    -- TOTAL RUBROS (Todos los rubros)
                    SUM(
                        CASE
                            WHEN parent_categ.id IS NOT null
                            THEN (aml.price_total *
                                CASE
                                    WHEN ldt.internal_type = 'credit_note' OR am.move_type = 'out_refund' THEN -1
                                    ELSE 1
                                END
                            )
                            ELSE 0
                        END
                    ) AS total_amount_rubro

                FROM account_move_line aml
                JOIN account_move am
                    ON aml.move_id = am.id
                LEFT JOIN account_move am_orig
                    ON am_orig.id = am.reversed_entry_id
                LEFT JOIN account_move am_base
                ON am_base.id = (
                    CASE
                    -- NC: si revierte algo, la base es:
                    --   * si revierte una ND con debit_origin_id -> la factura origen de esa ND
                    --   * si no -> el documento revertido (factura o ND sin origen)
                    WHEN am.move_type = 'out_refund' AND am.reversed_entry_id IS NOT NULL
                        THEN COALESCE(am_orig.debit_origin_id, am.reversed_entry_id)

                    -- ND: si tiene origen, base = factura origen
                    WHEN am.move_type = 'out_invoice' AND am.debit_origin_id IS NOT NULL
                        THEN am.debit_origin_id

                    -- Documento suelto: base = él mismo (así filtra por su propia fecha)
                    ELSE am.id
                    END
                )
                LEFT JOIN product_product pp
                    ON aml.product_id = pp.id
                LEFT JOIN product_template pt
                    ON pp.product_tmpl_id = pt.id
                LEFT JOIN product_category categ
                    ON pt.categ_id = categ.id
                -- Rubro = categoría padre si existe
                LEFT JOIN product_category parent_categ
                    ON parent_categ.id = categ.parent_id
                LEFT JOIN l10n_latam_document_type ldt
                    ON ldt.id = am.l10n_latam_document_type_id
                WHERE
                    am.state = 'posted'
                    AND am.move_type IN ('out_invoice', 'out_refund')      -- solo facturas y notas de crédito de cliente
                    AND aml.product_id IS NOT null
                    AND (
                        -- Facturas: por su propia fecha
                        (am.move_type = 'out_invoice'
                        AND am.invoice_date >= DATE '2026-01-01'
                        AND am.invoice_date <= DATE '2026-08-31')

                        OR

                        -- Notas de crédito: si están enlazadas, por la fecha de la factura original
                        (am.move_type = 'out_refund'
                        AND am.reversed_entry_id IS NOT NULL
                        AND am_base.invoice_date >= DATE '2026-01-01'
                        AND am_base.invoice_date <= DATE '2026-08-31')

                        OR

                        -- Notas de crédito manuales
                        (am.move_type = 'out_refund'
                        AND am.reversed_entry_id IS NULL
                        AND am.invoice_date >= DATE '2026-01-01'
                        AND am.invoice_date <= DATE '2026-08-31')
                    )
                    AND parent_categ.id IS NOT null 
	                AND aml.price_total <> 0
                GROUP BY
                    am.partner_id,
                    am.invoice_user_id,
                    am.currency_id
            )
        """ % self._table)
