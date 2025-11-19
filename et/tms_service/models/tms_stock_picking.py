from odoo import models, fields, api
from odoo.exceptions import ValidationError


class TmsStockPicking(models.Model):
    _name = 'tms.stock.picking'
    _description = 'Ruteo Stock Picking'

    picking_ids = fields.Many2many(
        'stock.picking',
        'tms_stock_picking_rel',   
        'tms_id',
        'picking_id',
        string='Referencias',
        help='Referencias de transferencias relacionadas'
    )
    fecha_entrega = fields.Datetime(string='Fecha de Carga')
    fecha_envio_wms = fields.Datetime(string='Fecha de Envío WMS')
    codigo_wms = fields.Char(string='Código WMS')
    doc_origen = fields.Char( string='Doc. Origen')
    partner_id = fields.Many2one('res.partner', string='Cliente')
    cantidad_bultos = fields.Float(string='Cantidad de Bultos')
    cantidad_lineas = fields.Integer(string='Linea de Pedido')
    carrier_id = fields.Many2one('delivery.carrier', string='Transportista')
    observaciones = fields.Text(string='Obs. de Operaciones')
    industry_id = fields.Many2one('res.partner.industry', string='Despacho')
    ubicacion = fields.Char(string='Ubicación')
    estado_digip = fields.Selection([('closed','Enviado y recibido'),
                                        ('done','Enviado'),
                                        ('no','No enviado'),
                                        ('error','Error envio'),
                                        ('pending','Pendiente')
                                    ], string='Estado WMS', default='no')
    estado_despacho = fields.Selection([('void', 'Anulado'),
                                        ('pending', 'Pendiente'),
                                        ('in_preparation', 'En Preparación'),
                                        ('prepared', 'Preparado'),
                                        ('delivered', 'Despachado'),
                                    ], string='Estado Despacho', default='pending')
    fecha_despacho = fields.Datetime(string='Fecha Despacho')
    observacion_despacho = fields.Text(string='Observaciones Despacho')
    contacto_calle = fields.Char(string='Contacto Calle')
    direccion_entrega = fields.Char(string='Dirección Entrega')
    contacto_cp = fields.Char(string='Contacto CP')
    contacto_ciudad = fields.Char(string='Contacto Ciudad')
    carrier_address = fields.Char(string='Transportista/Carrier Address')
    company_id = fields.Many2one('res.company', string='Compañia', default=lambda self: self.env.company)
    user_id = fields.Many2one('res.users', string='Usuario', default=lambda self: self.env.user)
    sale_id = fields.Many2one('sale.order', string='Pedido de Venta')
    delivery_state= fields.Selection([('no', 'No entregado'), ('delivered', 'Entregado'), ('returned', 'Devuelto')], default='no', copy=False, string='Estado de Entrega')
    
    #contador
    picking_count = fields.Integer(compute="_compute_counts", string="Transferencias")
    sale_count = fields.Integer(compute="_compute_counts", string="Venta")
    account_move_ids = fields.Many2many('account.move', string='Facturas')
    amount_totals = fields.Monetary(string='Total Facturas', store=True)
    items_ids = fields.Many2many('product.category', string='Rubros')
    currency_id = fields.Many2one('res.currency', string='Moneda', default=lambda self: self.env.company.currency_id)
    account_move_count = fields.Integer(compute="_compute_account_move_count", string="Facturas")
    
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

            rec.write({
                'estado_digip': stock_picking.state_wms,
                'estado_despacho': estado_despacho,
                'fecha_entrega': stock_picking.date_done,
                'delivery_state': stock_picking.delivery_state,
                'fecha_despacho': stock_picking.date_done,
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