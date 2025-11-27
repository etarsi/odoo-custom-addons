from odoo import fields, models, tools, api
from odoo.exceptions import AccessError
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
    
    @api.model
    def action_refresh_sql(self, *args, **kwargs):
        self.env.cr.execute("SELECT count(*) FROM report_debt_composition_client_tbl;")
        before_count = self.env.cr.fetchone()[0]
        self.env.cr.execute("SELECT public.refresh_report_debt_composition_client();")
        self.env.cr.execute("SELECT count(*) FROM report_debt_composition_client_tbl;")
        after_count = self.env.cr.fetchone()[0]
        _logger.info(f"Refreshed report_debt_composition_client: before_count={before_count}, after_count={after_count}")
        self.env.cr.commit()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def init(self):
        cr = self.env.cr
        cr.execute("SELECT public.refresh_report_debt_composition_client();")
        self.env.cr.commit()
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
            FROM report_debt_composition_client_tbl;
        """)

class ReportDebtCompositionClientCompany(models.Model):
    _name = "report.debt.composition.client.company"
    _auto = False
    _description = "Composición de deuda cliente por compañías"
    _order = 'company_id, fecha asc, nombre asc'

    partner = fields.Many2one('res.partner', string='Cliente', readonly=True)
    fecha = fields.Date(string='Fecha', readonly=True)
    fecha_vencimiento = fields.Date(string='Fecha Vencimiento', readonly=True)
    nombre = fields.Char(string='Comprobante', readonly=True)
    comercial = fields.Many2one('res.users', string="Comercial", readonly=True)
    ejecutivo = fields.Many2one('res.users', string="Ejecutiva", readonly=True)
    importe_original = fields.Monetary(string='Importe Original', readonly=True, currency_field='currency_id')
    importe_residual = fields.Monetary(string='Importe Residual', readonly=True, currency_field='currency_id')
    importe_aplicado = fields.Monetary(string='Importe Aplicado', readonly=True, currency_field='currency_id')
    saldo_acumulado = fields.Monetary(string='Saldo Acumulado', readonly=True, currency_field='currency_id')
    origen = fields.Selection([
        ('factura', 'Factura'),
        ('nota_credito', 'Nota de Crédito'),
        ('recibo', 'Recibo')
    ], string='Origen', readonly=True)
    company_id = fields.Many2one('res.company', string='Compañía', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', readonly=True)
    
    
    def action_refresh_sql(self, partner_id=None, company_ids=None):
        cr = self.env.cr
        if not company_ids:
            company_ids = None

        cr.execute("""
            SELECT public.refresh_report_debt_composition_client_company_ids(%s, %s);
        """, (partner_id, company_ids))
        self.env.cr.commit()
        _logger.info("Refreshed report_debt_composition_client: partner_id=%s company_ids=%s", partner_id, company_ids)
        return True
    
    def init(self):
        cr = self.env.cr
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
            FROM report_debt_composition_client_company_ids_tbl;
        """)