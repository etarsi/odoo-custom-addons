from odoo import fields, models, tools
import logging
_logger = logging.getLogger(__name__)

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
        # timeouts cortos (no crítico si falla)
        try:
            cr.execute("SET LOCAL lock_timeout = '5s'; SET LOCAL statement_timeout = '60000';")
        except Exception:
            pass

        # --- 1) Buscar la función por pg_proc (con schema) ---
        cr.execute("""
            SELECT n.nspname || '.' || p.proname AS fqname
            FROM pg_proc p
            JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE p.proname = 'refresh_report_debt_composition_client'
              AND pg_get_function_identity_arguments(p.oid) = '';
        """)
        row = cr.fetchone()
        if row:
            fqfunc = row[0]  # ej. "public.refresh_report_debt_composition_client"
            _logger.info("Ejecutando función SQL: %s()", fqfunc)
            try:
                cr.execute(f"SELECT {fqfunc}();")
            except Exception:
                _logger.info("Falló el refresh_report_debt_composition_client()")
        else:
            _logger.info("Función refresh_report_debt_composition_client() no encontrada en ningún schema; salto el refresh")

        # --- 2) Recrear la vista que Odoo lee ---
        tools.drop_view_if_exists(cr, self._table)
        cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS
            SELECT 
                id,
                partner,
                fecha,
                fecha_vencimiento,
                nombre,
                comercial,
                ejecutivo,
                importe_original,
                importe_residual,
                importe_aplicado,
                saldo_acumulado,
                origen,
                company_id,
                currency_id
            FROM report_debt_composition_client_tbl WHERE company_id = 1;
        """)
        _logger.info("Vista %s creada/actualizada correctamente", self._table)