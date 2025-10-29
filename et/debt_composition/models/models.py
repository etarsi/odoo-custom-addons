from odoo import fields, models, tools

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
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS
            SELECT * FROM report_debt_composition_client_tbl;
        """)