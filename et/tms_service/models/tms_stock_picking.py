from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class TmsStockPicking(models.Model):
    _name = 'tms.stock.picking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Ruteo Stock Picking'

    name = fields.Char(string='Referencia', required=True, copy=False, index=True, default=lambda self: _("New"), tracking=True)
    picking_ids = fields.Many2many(
        'stock.picking',
        'tms_stock_picking_rel',   
        'tms_id',
        'picking_id',
        string='Referencias',
        help='Referencias de transferencias relacionadas',
        tracking=True
    )
    fecha_entrega = fields.Datetime(string='Fecha de Carga', index=True, tracking=True)
    fecha_envio_wms = fields.Datetime(string='Fecha de Envío WMS', tracking=True)
    codigo_wms = fields.Char(string='Código WMS', tracking=True)
    doc_origen = fields.Char( string='Doc. Origen', tracking=True)
    partner_id = fields.Many2one('res.partner', string='Cliente', tracking=True)
    cantidad_bultos = fields.Float(string='Cantidad de Bultos', tracking=True)
    cantidad_lineas = fields.Integer(string='Linea de Pedido', tracking=True)
    carrier_id = fields.Many2one('delivery.carrier', string='Transportista', tracking=True)
    observaciones = fields.Text(string='Obs. de Operaciones', tracking=True)
    industry_id = fields.Many2one('res.partner.industry', string='Despacho', tracking=True)
    ubicacion = fields.Char(string='Ubicación', tracking=True)
    estado_digip = fields.Selection(selection=[
            ('no', 'No enviado'),
            ('sent', 'Enviado'),
            ('received', 'Recibido')
        ], string='Estado WMS', default='no', tracking=True)


    estado_despacho = fields.Selection([('void', 'Anulado'),
                                        ('pending', 'Pendiente'),
                                        ('in_preparation', 'En Preparación'),
                                        ('prepared', 'Preparado'),
                                        ('delivered', 'Despachado'),
                                    ], string='Estado Despacho', default='pending', tracking=True)
    fecha_despacho = fields.Datetime(string='Fecha Despacho', tracking=True)
    observacion_despacho = fields.Text(string='Observaciones Despacho', tracking=True)
    contacto_calle = fields.Char(string='Contacto Calle', tracking=True)
    direccion_entrega = fields.Char(string='Dirección Entrega', tracking=True)
    contacto_cp = fields.Char(string='Contacto CP', tracking=True)
    contacto_ciudad = fields.Char(string='Contacto Ciudad', tracking=True)
    carrier_address = fields.Char(string='Transportista/Carrier Address', tracking=True)
    company_id = fields.Many2one('res.company', string='Compañia', default=lambda self: self.env.company, tracking=True)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user, tracking=True)
    sale_id = fields.Many2one('sale.order', string='Pedido de Venta', tracking=True)
    delivery_state= fields.Selection([('no', 'No entregado'), 
                                        ('delivered', 'Entregado'), 
                                        ('returned', 'Devuelto')], default='no', copy=False, string='Estado de Entrega', tracking=True)
    
    #contador
    picking_count = fields.Integer(compute="_compute_counts", string="Transferencias", tracking=True)
    sale_count = fields.Integer(compute="_compute_counts", string="Venta", tracking=True)
    account_move_ids = fields.Many2many('account.move', string='Facturas', tracking=True)
    amount_totals = fields.Monetary(string='Total Facturado', store=True, tracking=True)
    amount_nc_totals = fields.Monetary(string='Total N. Crédito', store=True, tracking=True)
    items_ids = fields.Many2many('product.category', string='Rubros', tracking=True)
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    account_move_count = fields.Integer(compute="_compute_account_move_count", string="Facturas", tracking=True)
    invoice_status = fields.Selection([
        ('no_invoice', 'Sin factura'),
        ('draft', 'Solo borrador'),
        ('posted', 'Solo confirmadas'),
        ('cancel', 'Solo canceladas'),
        ('mixed', 'Mixto'),
    ], string='Estado Facturas', compute='_compute_invoice_status', store=True, tracking=True)
    
    
    @api.depends('account_move_ids', 'account_move_ids.state')
    def _compute_invoice_status(self):
        for rec in self:
            moves = rec.account_move_ids
            if not moves:
                rec.invoice_status = 'no_invoice'
                continue

            states = set(moves.mapped('state'))
            if states == {'draft'}:
                rec.write({'invoice_status': 'draft'})
            elif states == {'posted'}:
                rec.write({'invoice_status': 'posted'})
            elif states == {'cancel'}:
                rec.write({'invoice_status': 'cancel'})
            else:
                rec.write({'invoice_status': 'mixed'})
    
    def _compute_account_move_count(self):
        for rec in self:
            rec.account_move_count = len(rec.account_move_ids)

    def _compute_counts(self):
        for rec in self:
            rec.picking_count = len(rec.picking_ids)
            rec.sale_count = 1 if rec.sale_id else 0

    def action_open_pickings(self):
        self.ensure_one()
        action = self.env.ref('stock.action_picking_tree_all').read()[0]
        action['domain'] = [('id', 'in', self.picking_ids.ids)]
        action['context'] = {'search_default_group_by_picking_type': 0}
        return action

    def action_open_sale(self):
        self.ensure_one()
        if not self.sale_id:
            return False
        # Si hay sale_id, abrir directo su formulario
        action = self.env.ref('sale.action_orders').read()[0]
        action.update({
            'views': [(self.env.ref('sale.view_order_form').id, 'form')],
            'res_id': self.sale_id.id,
            'domain': [('id', '=', self.sale_id.id)],
        })
        return action
    
    def action_open_account_moves(self):
        self.ensure_one()
        if not self.account_move_ids:
            return False
        action = self.env.ref('account.action_move_out_invoice_type').read()[0]
        action['domain'] = [('id', 'in', self.account_move_ids.ids)]
        return action
    
    def action_forzar_actualizacion_tms(self):
        # Recolecto códigos válidos (no vacíos)
        codigos = [c for c in self.mapped('codigo_wms') if c]

        # Busco todos los pickings de una
        pickings = self.env['stock.picking'].sudo().search([('codigo_wms', 'in', codigos)])
        sp_by_code = {p.codigo_wms: p for p in pickings}

        updated = 0
        skipped_no_code = 0
        skipped_not_found = 0

        for rec in self:
            if not rec.codigo_wms:
                skipped_no_code += 1
                continue

            stock_picking = sp_by_code.get(rec.codigo_wms)
            if not stock_picking:
                skipped_not_found += 1
                continue

            # Mapeo de estado
            estado_despacho = 'pending'
            if stock_picking.state_wms == 'done':
                estado_despacho = 'in_preparation'
            elif stock_picking.state_wms == 'closed' and stock_picking.delivery_state == 'no':
                estado_despacho = 'prepared'
            elif stock_picking.state_wms == 'closed' and stock_picking.delivery_state == 'delivered':
                estado_despacho = 'delivered'
            elif stock_picking.state_wms == 'error':
                estado_despacho = 'void'
            elif stock_picking.state == 'cancel':
                estado_despacho = 'void'

            invoices = self.env['account.move'].browse(stock_picking.invoice_ids.ids)
            rubros_ids = []
            rube_ids_final = []
            amount_total = 0
            amount_nc_total = 0
            if invoices:
                for invoice in invoices:
                    #separar facturas de cliente y notas de credito
                    if invoice.move_type == 'out_refund' and invoice.state != 'cancel':
                        amount_nc_total += invoice.amount_total
                    elif invoice.move_type == 'out_invoice' and invoice.state != 'cancel':
                        amount_total += invoice.amount_total
                    items = invoice.invoice_line_ids.mapped('product_id.categ_id.parent_id')
                    # Filtrar categorías nulas y obtener solo los ids únicos
                    items = items.filtered(lambda c: c and c.id).ids
                    #setear los rubros en el tms_stock_picking
                    rubros_ids = list(set(rubros_ids + items))

                #quitar los rubros duplicados
                rube_ids_final = list(set(rubros_ids))
            # amount_nc debe ser negativo
            amount_nc_total = -abs(amount_nc_total)
            rec.write({
                'estado_digip': stock_picking.state_wms,
                'estado_despacho': estado_despacho,
                'fecha_entrega': stock_picking.date_done,
                'delivery_state': stock_picking.delivery_state,
                'fecha_despacho': stock_picking.date_done,
                'account_move_ids': [(6, 0, stock_picking.invoice_ids.ids)],
                'amount_totals': amount_total,
                'amount_nc_totals': amount_nc_total,
                'items_ids': rube_ids_final,
            })
            updated += 1

        # Notificación (no interrumpe aunque no haya códigos)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Actualización TMS',
                'message': (
                    f'Actualizados: {updated} | '
                    f'Sin código: {skipped_no_code} | '
                    f'Código sin picking: {skipped_not_found}'
                ),
                'type': 'success',
                'sticky': False,
            }
        }
        
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code("tms.stock.picking") or _("New")
        return super().create(vals_list)