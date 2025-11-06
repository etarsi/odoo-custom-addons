from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round, float_compare  # Importa float_round si lo necesitas
# from odoo.tools import float_compare  # Elimina esta línea si no usas float_compare
import math 
import logging
_logger = logging.getLogger(__name__)

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    RUBRO_COMPANY_MAPPING = {
        'JUGUETES': 3,
        'CARPAS': 3,
        'RODADOS INFANTILES': 3,
        'PISTOLA DE AGUA': 4,
        'INFLABLES': 4,
        'PELOTAS': 4,
        'VEHICULOS A BATERIA': 4,
        'RODADOS': 2,
        'MAQUILLAJE': 2,
        'CABALLITOS SALTARINES': 2,
    }

    # inherited
    note = fields.Html('Terms and conditions')
    pricelist_id = fields.Many2one(
        'product.pricelist', string='Lista de Precios', check_company=True,  # Unrequired company
        required=True, readonly=True, states={'draft': [('readonly', False)], 'sent': [('readonly', False)], 'sale': [('readonly', False)],},
        domain="['|', ('company_id', '=', False), ('company_id', '=', company_id)]", tracking=1,
        help="If you change the pricelist, only newly added lines will be affected.")

    # custom
    special_price = fields.Boolean('Precios especiales')
    order_subtotal = fields.Float('Subtotal', compute='_compute_subtotal', readonly=True)
    global_discount = fields.Float('Descuento', default=0)
    old_sale = fields.Boolean(default=False, copy=False)
    old_sale_txt = fields.Text(default='⚠️ PEDIDO VIEJO - FACTURAR DE LA VIEJA FORMA')
    is_misiones = fields.Boolean(default=False, copy=False)
    warning_txt = fields.Text(default='⚠️ EL CLIENTE PERTENECE A MISIONES')
    items_ids = fields.Many2many(
        'product.category', string='Rubros', compute='_compute_items_ids', store=True, readonly=False,
        help="Rubros de los productos en la orden de venta. Se usa para filtrar productos en la vista de formulario."
    )

    def unlink(self):
        for order in self:
            if order.state not in ['draft']:
                raise UserError(_(
                    "No se puede borrar el pedido %s porque ya fue confirmado o procesado.") % order.name)

            order.unreserve_stock_sale_order()

        return super().unlink()
    

    def unreserve_stock_sale_order(self):
        for record in self:
            stock_moves_erp = self.env['stock.moves.erp'].search([('sale_id', '=', record.id)])

            if stock_moves_erp:
                for stock in stock_moves_erp:
                    stock.unreserve_stock()


    def cancel_order(self):
        for record in self:
            if record.picking_ids:
                for picking in record.picking_ids:
                    if picking.state_wms != 'no':
                        raise UserError('No se puede cancelar el pedido de venta porque hay transferencias que están enviadas a Digip')
                
                record.cancel_pickings()
                record.unreserve_stock_sale_order()
                record.action_cancel()

    
    def cancel_pickings(self):
        for record in self:
            for picking in record.picking_ids:
                for move in picking.move_ids_without_package:
                    move.state = 'draft'
                    move.quantity_done = 0
                    move.unlink()
                picking.state = 'draft'
                picking.unlink()

    # OVERRIDE DE ONCHANGE
    @api.onchange("partner_id")
    def onchange_partner_id(self):
        res = super().onchange_partner_id()
        if self.partner_id:
            self.check_price_list()
        self.condicion_venta = self.partner_id.condicion_venta
        self.condicion_m2m_numeric = False
        return res

    @api.onchange('partner_shipping_id')
    def _onchange_partner_shipping_id(self):
        self.check_partner_origin()


    @api.onchange('pricelist_id')
    def _onchange_pricelist_id(self):
        for record in self:
            record.update_lines_prices()


    @api.onchange('condicion_m2m')
    def _onchange_condicion_m2m(self):
        for record in self:
            if record.condicion_m2m.name == 'TIPO 3':
                pricelist = self.env['product.pricelist'].search([('list_default_b','=', True)])
                if pricelist:
                    record.pricelist_id = pricelist.id
                    discounts = {}

                    for line in record.order_line:
                        line.tax_id = False
                        discounts[line.id] = line.discount
                        
                    record.update_prices()
                    
                    for line in record.order_line:
                        if line.id in discounts:
                            line.discount = discounts[line.id]
                else: 
                    raise UserError("No se encontró precio de lista con ID 46")


    @api.onchange('global_discount')
    def _onchange_discount(self):
        for record in self:
            record.update_lines_discount()


    @api.onchange('order_line')
    def _onchange_lines_bultos(self):
        for record in self:
            record.packaging_qty = 0
            for line in record.order_line:
                record.packaging_qty += line.product_packaging_qty

    ### DEPENDS

    @api.depends('amount_tax', 'amount_untaxed', 'order_line.tax_id')
    def _compute_subtotal(self):
        for record in self:
            if not record.order_line:
                record.order_subtotal = record.amount_untaxed
                continue  
            taxes_found = any(
                tax.id in [62, 185, 309, 433] for line in record.order_line for tax in line.tax_id
            )

            record.order_subtotal = record.amount_untaxed * 1.21 if taxes_found else record.amount_untaxed

    @api.model
    def create(self, vals):

        self.check_partner_origin()
        # --- Config compañía destino ---
        #company_produccion_b = self.env['res.company'].browse(1)
        # --- Resolver condición (Many2one) ---
        #cond_model = self.env['condicion.venta']  # ajustá el modelo si se llama distinto
        #cond_name = cond_model.browse(vals.get('condicion_m2m')).name or ''

        # --- Forzar compañía/depósito en vals si corresponde (TIPO 3) ---
        #force_company = (cond_name.strip().upper() == 'TIPO 3')
        #current_company_id = vals.get('company_id')

        #env_create = self
        #if force_company and current_company_id != company_produccion_b.id:
        #    wh = self.env['stock.warehouse'].search([('company_id', '=', company_produccion_b.id)], limit=1)
        #    if not wh:
        #        raise UserError(_("No se encontró un depósito para la compañía %s.") % company_produccion_b.display_name)

        #    vals = dict(vals)  # copiar para no mutar
        #    vals['company_id'] = company_produccion_b.id
        #    vals['warehouse_id'] = wh.id

            # Crear bajo el contexto/compañía destino para evitar conflictos multi-company
        #    env_create = self.with_context(allowed_company_ids=[company_produccion_b.id]).with_company(company_produccion_b)
        order = super().create(vals)
        # validar la linea de productos si tienen el mismo rubo que pertenece a la compañia si es company_id = 1 no entra por aca
        #if order.company_id.id != 1:
        #    for line in order.order_line:
        #        rubro = line.product_id.categ_id.parent_id.name.upper().strip()
        #        if rubro in self.RUBRO_COMPANY_MAPPING:
        #            expected_company_id = self.RUBRO_COMPANY_MAPPING[rubro]
        #            if order.company_id.id != expected_company_id:
        #                raise UserError(_("La línea de producto %s pertenece al rubro %s que debe estar en la compañía con ID %s, pero la orden está en la compañía con ID %s.") % (
        #                    line.product_id.display_name, rubro, expected_company_id, order.company_id.id))
        
        #company_produccion_b = self.env['res.company'].browse(1)
        #if self.company_id.id != company_produccion_b.id and self.condicion_m2m.name == 'TIPO 3':
        #    warehouse = self.env['stock.warehouse'].search([('company_id', '=', company_produccion_b.id)], limit=1)
        #    self.write({'company_id': company_produccion_b.id})
        #    self.write({'warehouse_id': warehouse.id})
        #    for line in self.order_line:
        #        if line.company_id.id != company_produccion_b.id:
        #            line.write({'company_id': company_produccion_b.id})
        #    self.message_post(body=_("Compañía cambiada a %s en el pedido y todas sus líneas durante la creación.") % self.company_id.name)
        order.check_order()
        if not order.message_ids:
            order.message_post(body=_("Orden de venta creada."))
        return order

    def action_confirm(self):
        res = super().action_confirm()
        for record in self:
            company_letter = record._get_company_letter(record)

            record.name = f"{record.name} - {company_letter}"

            for picking in record.picking_ids:
                picking.origin = record.name

            if company_letter == 'P':               
                pricelist = self.env['product.pricelist'].search([('list_default_b','=', True)])
                if pricelist:
                    record.pricelist_id = pricelist.id
                    discounts = {}
                    for line in record.order_line:
                        discounts[line.id] = line.discount
                        
                    record.update_prices()
                    
                    for line in record.order_line:
                        if line.id in discounts:
                            line.discount = discounts[line.id]
                else: 
                    raise UserError(f"No se encontró precio de lista por defecto")
            

            # STOCK ERP

            up = record.check_unavailable_products()

            if up:
                record.clean_stock_moves(up)


        return res
    

    def update_prices(self):
        self.ensure_one()
        if not self.special_price:
            for line in self._get_update_prices_lines():
                line.product_uom_change()
                line.discount = 0
                line._onchange_discount()
        self.show_update_pricelist = False



    def check_unavailable_products(self):
        for record in self:
            up = []
            if record.order_line:
                for line in record.order_line:
                    if not line.is_available:
                        up.append(line.product_id.id)

            return up

    def clean_stock_moves(self, up):
        for record in self:
            for picking in record.picking_ids:
                if picking.move_ids_without_package:
                    for move in picking.move_ids_without_package:
                        if move.product_id.id in up:
                            move.state = 'draft'
                            move.unlink()
                picking.show_operations = False


    def check_partner_origin(self):
        for record in self:
            if record.partner_shipping_id.state_id.id == 566:
                record.is_misiones = True
            else:
                record.is_misiones = False


    def _get_company_letter(self, order):
        company_id = order.company_id
        l = 'P'

        if company_id.id == 2:
            l = 'S'
        elif company_id.id == 3:
            l = 'B'
        elif company_id.id == 4:
            l = 'F'

        return l
      

    def check_order(self):
        for record in self:            
            record.check_comercial_id() # Forzar comercial correcto
            record.check_price_list()
            record.update_lines_discount()
            record.update_lines_prices()
            record.check_taxes()


    def check_taxes(self):
        for record in self:
            if record.condicion_m2m.name == 'TIPO 3':
                for line in record.order_line:
                    line.tax_id = False


    def check_comercial_id(self):
        for record in self:
            comercial_id = record.partner_id.user_id
            if comercial_id:
                record.user_id = comercial_id 


    def check_price_list(self):
        for record in self:
            _logger.info(f"Checking pricelist for order {record.name} and partner {record.partner_id.name}")
            if record.condicion_m2m.name == 'TIPO 3':
                pricelist = self.env['product.pricelist'].search([('list_default_b','=', True)], limit=1)
                if pricelist:
                    _logger.info(f"Setting pricelist {pricelist.name} for order {record.name}")
                    record.pricelist_id = pricelist.id
            else:
                pricelist = self.env['product.pricelist'].search([('is_default','=', True)], limit=1)
                if pricelist:
                    _logger.info(f"Setting default pricelist {pricelist.name} for order {record.name}")
                    record.pricelist_id = pricelist.id
            _logger.info(f"Pricelist for order {record.name} set to {record.pricelist_id.name}")

    def update_lines_prices(self):
        for record in self:
            if record.order_line and not record.special_price:
                discounts = {}
                for line in record.order_line:
                    discounts[line.id] = line.discount
                    
                record.update_prices()
                
                for line in record.order_line:
                    if line.id in discounts:
                        line.discount = discounts[line.id]


    def update_lines_discount(self):
        for record in self:
            if record.order_line:
                for line in record.order_line:
                    line.discount = record.global_discount

    @api.model
    def _default_note(self):
        return
    
    #COMPUTES

    

    @api.depends('order_line.product_id')
    def _compute_items_ids(self):
        for record in self:
            if record.order_line:
                # Obtener todas las categorías padre únicas de los productos en las líneas de pedido
                items = record.order_line.mapped('product_id.categ_id.parent_id')
                # Filtrar categorías nulas y obtener solo los ids únicos
                items = items.filtered(lambda c: c and c.id).ids
                record.items_ids = [(6, 0, items)]
            else:
                record.items_ids = [(5, 0, 0)]

class SaleOrderLineInherit(models.Model):
    _inherit = 'sale.order.line'

    qty_to_invoice = fields.Float(
        compute='_get_to_invoice_qty', string='To Invoice Quantity', store=True,
        digits='Product Unit of Measure', readonly=False)
    qty_invoiced = fields.Float(
        compute='_compute_qty_invoiced', string='Invoiced Quantity', store=True,
        digits='Product Unit of Measure', readonly=False)

    is_available = fields.Boolean(string='Disponible', compute="_compute_is_available", store=True)
    is_cancelled = fields.Boolean(default=False)
    disponible_unidades = fields.Integer('Disponible')
    is_compromised = fields.Boolean(default=False)
    stock_erp = fields.Many2one('stock.erp')
    stock_moves_erp = fields.Many2one('stock.moves.erp')
    
    def create(self, vals):
        res = super().create(vals)
        for rec in res:
            if rec.product_id:
                if rec.product_id.display:
                    amount_display = rec.product_uom_qty/rec.product_id.display
                    has_decimals = abs(amount_display - round(amount_display)) > 1e-9
                    if has_decimals:
                        raise ValidationError(f"La cantidad del producto {rec.product_id.default_code} a ingresar, no corresponde con las cantidades del display {rec.product_id.display}")
                rec.alert_decimal_qty()
                # Validar si el producto tiene el sale_ok true
                if not rec.product_id.sale_ok:
                    raise ValidationError(_("Este producto no esta habilitado para la venta con este código: %s", rec.product_id.default_code))
                # Si no hay un producto_packaging_id definido, asigna el primero del producto
                if not rec.product_packaging_id:
                    if rec.product_id.packaging_ids:
                        rec.product_packaging_id = rec.product_id.packaging_ids[0]
                        rec.product_packaging_qty = rec.product_uom_qty / rec.product_packaging_id.qty
                rec.update_stock_erp()
                # rec.check_client_purchase_intent()
                rec.comprometer_stock()
                
        return res
    
    def unlink(self):
        for record in self:
            if record.state == 'draft':
                stock_moves_erp_res = self.env['stock.moves.erp'].search([('sale_line_id', '=', record.id), ('type', '=', 'reserve')], limit=1)

                if stock_moves_erp_res:
                    stock_moves_erp_res.unreserve_stock()

                return super().unlink()
        
    def unreserve_stock(self):
        for record in self:
            stock_moves_erp_prep = self.env['stock.moves.erp'].search([('sale_line_id', '=', record.id), ('type', '=', 'preparation')])
            if stock_moves_erp_prep:
                raise UserError(f'No puede borrar o liberar stock de una linea que está siendo preparada. Código: [{record.product_id.code}] {record.product_id.name}')
            
            stock_moves_erp_res = self.env['stock.moves.erp'].search([('sale_line_id', '=', record.id), ('type', '=', 'reserve')], limit=1)

            if stock_moves_erp_res:
                stock_moves_erp_res.unreserve_stock()

            if record.state == 'draft':
                record.unlink()

    def update_stock_erp(self):
        for record in self:
            default_code = record.product_id.default_code

            if default_code:
                if default_code.startswith('9'):
                    search_code = default_code[1:]
                else:
                    search_code = default_code

                stock_erp = self.env['stock.erp'].search([
                    ('product_id.default_code', '=', search_code)
                ], limit=1)

                if stock_erp:
                    record.disponible_unidades = stock_erp.disponible_unidades
                else:
                    record.disponible_unidades = 0.0
            else:
                record.disponible_unidades = 0.0

        

    def check_client_purchase_intent(self):
        for record in self:
            if not record.is_available:

                client_purchase_intent = self.env['client.purchase.intent']
                cpi = client_purchase_intent.search([('sale_line_id', '=', record.id)], limit=1)

                if cpi:
                    cpi.quantity = record.product_uom_qty
                else:
                    vals = {}
                    vals['sale_id'] = record.order_id.id
                    vals['sale_line_id'] = record.id
                    vals['partner_id'] = record.order_id.partner_id.id
                    vals['product_id'] = record.product_id.id
                    vals['quantity'] = record.product_uom_qty
                    vals['uxb'] = record.product_id.packaging_ids[0].qty

                    client_purchase_intent.create(vals)


    def comprometer_stock(self):
        for record in self:
            if record.is_available:
                vals = {}

                default_code = record.product_id.default_code

                if default_code:
                    if default_code.startswith('9'):
                        search_code = default_code[1:]
                    else:
                        search_code = default_code

                    product_id = self.env['product.product'].search([
                        ('default_code', '=', default_code)
                    ], limit=1)

                    stock_erp = self.env['stock.erp'].search([
                        ('product_id.default_code', '=', search_code)
                    ], limit=1)

                
                vals['stock_erp'] = stock_erp.id
                vals['sale_id'] = record.order_id.id
                vals['sale_line_id'] = record.id
                vals['partner_id'] = record.order_id.partner_id.id
                vals['product_id'] = product_id.id
                vals['quantity'] = record.product_uom_qty
                vals['uxb'] = record.product_packaging_id.qty or ''
                vals['bultos'] = record.product_packaging_qty
                vals['type'] = 'reserve'

                stock_moves_erp = self.env['stock.moves.erp'].create(vals)

                record.is_compromised = True

    def comprometer_stock2(self):
        for record in self:
            if record.is_available:
                vals = {}

                default_code = record.product_id.default_code

                if default_code:
                    if default_code.startswith('9'):
                        search_code = default_code[1:]
                    else:
                        search_code = default_code

                    product_id = self.env['product.product'].search([
                        ('default_code', '=', default_code)
                    ], limit=1)

                    stock_erp = self.env['stock.erp'].search([
                        ('product_id.default_code', '=', search_code)
                    ], limit=1)

                
                vals['stock_erp'] = stock_erp.id
                vals['sale_id'] = record.order_id._origin.id
                vals['sale_line_id'] = record._origin.id
                vals['partner_id'] = record.order_id.partner_id.id
                vals['product_id'] = product_id.id
                vals['quantity'] = record.product_uom_qty
                vals['uxb'] = record.product_packaging_id.qty or ''
                vals['bultos'] = record.product_packaging_qty
                vals['type'] = 'reserve'

                self.env['stock.moves.erp'].create(vals)

                record.is_compromised = True

    # COMPUTED

    @api.depends('disponible_unidades', 'product_uom_qty')
    def _compute_is_available(self):
        for record in self:
                stock_moves_erp = self.env['stock.moves.erp'].search([('sale_line_id', '=', record.id), ('type', '=', 'reserve')], limit=1)

                if stock_moves_erp: # esta comprometido
                    disponible_real = stock_moves_erp.quantity + record.disponible_unidades
                    if record.product_uom_qty <= disponible_real:
                        record.is_available = True
                    else:
                        record.is_available = False


                else: # no esta comprometido
                    if record.product_uom_qty <= record.disponible_unidades:
                        record.is_available = True
                    else:
                        record.is_available = False

    


    @api.onchange('product_id')
    def _onchange_availability(self):
        for record in self:
            record.update_stock_erp()


    def _update_line_quantity(self, values):
        orders = self.mapped('order_id')
        for order in orders:
            order_lines = self.filtered(lambda x: x.order_id == order)
            msg = "<b>" + _("The ordered quantity has been updated.") + "</b><ul>"
            for line in order_lines:
                msg += "<li> %s: <br/>" % line.product_id.display_name
                msg += _(
                    "Ordered Quantity: %(old_qty)s -> %(new_qty)s",
                    old_qty=line.product_uom_qty,
                    new_qty=values["product_uom_qty"]
                ) + "<br/>"
                if line.product_id.type in ('consu', 'product'):
                    msg += _("Delivered Quantity: %s", line.qty_delivered) + "<br/>"
                msg += _("Invoiced Quantity: %s", line.qty_invoiced) + "<br/>"
            msg += "</ul>"
            # order.message_post(body=msg)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for record in self:

            if record.company_id.id == 1:
                record.write(
                    {
                        'tax_id': False,
                    }
                )
                

            record.discount = record.order_id.global_discount
            packaging_ids = record.product_id.packaging_ids
            if packaging_ids:
                record.write(
                            {
                                'product_packaging_id': packaging_ids[0],
                            })
                        
    ## DESHABILITAR ADVERTENCIA DE UNIDAD X BULTO                    
    @api.onchange('product_packaging_id')
    def _onchange_product_packaging_id(self):
        return    

    @api.onchange('product_packaging_id', 'product_uom', 'product_uom_qty')
    def _onchange_update_product_packaging_qty(self):
        # Solo recalcula bultos si NO venimos del onchange de bultos
        if self._context.get('from_packaging_qty'):
            return
        # Procesamos cada línea con el contexto ajustado para evitar bucle
        lines_with_context = self.with_context(from_uom_qty=True)
        for line in lines_with_context:
            line.alert_decimal_qty()
            so_config = line.env['sale.order.settings'].browse(1)
            if not line.product_packaging_id or not line.product_packaging_id.qty:
                line.product_packaging_qty = False
            else:
                line.product_packaging_qty = line.product_uom_qty / line.product_packaging_id.qty


            if line.product_uom_qty > 0:
                if line._origin and line._origin.id and line.product_id:
                    in_preparation = self.env['stock.moves.erp'].search([('sale_line_id', '=', line._origin.id), ('type', '=', 'preparation')], limit=1)

                    if in_preparation:
                        raise UserError('No se puede actualizar las cantidades porque ya están siendo preparadas o ya fueron entregadas')

                    stock_moves_erp = self.env['stock.moves.erp'].search([('sale_line_id', '=', line._origin.id), ('type', '=', 'reserve')], limit=1)

                    if stock_moves_erp:
                        if line.product_uom_qty < stock_moves_erp.quantity:
                            diferencia = stock_moves_erp.quantity - line.product_uom_qty
                            stock_moves_erp.quantity = line.product_uom_qty
                            stock_erp = stock_moves_erp.stock_erp
                            stock_erp.write({
                                'comprometido_unidades': stock_erp.comprometido_unidades - diferencia
                            })
                            
                            stock_moves_erp.update_sale_orders()
                            line.update_stock_erp()                            
                            line._compute_is_available()

                        else:
                            disponible_real = stock_moves_erp.quantity + line.disponible_unidades                    
                            if line.product_uom_qty <= disponible_real:                 
                                diferencia = line.product_uom_qty - stock_moves_erp.quantity
                                
                                stock_moves_erp.quantity = line.product_uom_qty
                                stock_erp = stock_moves_erp.stock_erp
                                stock_erp.write({
                                    'comprometido_unidades': stock_erp.comprometido_unidades + diferencia
                                })
                                stock_moves_erp.update_sale_orders()
                                line.update_stock_erp()
                                line._compute_is_available()
                                
                            else:
                                raise UserError(f'No puede comprometer más cantidades de las disponibles. Actualmente tiene comprometidas: {stock_moves_erp.quantity} y quedan disponibles para agregar: {line.disponible_unidades}')
                        
                    else:
                        line.update_stock_erp()
                        if line.product_uom_qty <= line.disponible_unidades:
                            line.comprometer_stock2()
                            line.update_stock_erp()
                            line._compute_is_available()
                        else:
                            raise UserError('No se puede comprometer más unidades de las disponibles.')


        

    @api.onchange('product_packaging_qty')
    def _onchange_product_packaging_qty(self):
        # Solo recalcula unidades si NO venimos del onchange de unidades
        if self._context.get('from_uom_qty'):
            return
        # Procesamos cada línea con el contexto ajustado para evitar bucle
        lines_with_context = self.with_context(from_packaging_qty=True)
        for line in lines_with_context:
            if line.product_packaging_id and line.product_uom:
                packaging_uom = line.product_packaging_id.product_uom_id
                qty_per_packaging = line.product_packaging_id.qty
                product_uom_qty = packaging_uom._compute_quantity(self.product_packaging_qty * qty_per_packaging, self.product_uom)
                if float_compare(product_uom_qty, self.product_uom_qty, precision_rounding=self.product_uom.rounding) != 0:
                    # Validar si product_uom_qty tiene decimales
                    if product_uom_qty != int(product_uom_qty):
                        # Calcular sugerencias: entero inferior y superior
                        floor_qty = math.floor(product_uom_qty)
                        ceil_qty = math.ceil(product_uom_qty)
                        # Mensaje personalizado
                        raise ValidationError(
                            f"La cantidad de unidades se transformó a {product_uom_qty:.2f}, que tiene decimales. "
                            f"Por favor, ajuste las unidades. Podría colocar {floor_qty} o {ceil_qty}."
                        )
                    self.product_uom_qty = product_uom_qty

    def alert_decimal_qty(self):
        for line in self:
            if line.product_uom_qty:
                if line.product_uom_qty != int(line.product_uom_qty):
                    raise ValidationError(
                        f"No se aceptan unidades con valores decimales: {line.product_uom_qty:.2f}."
                )

    
class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'

    # heredado
    property_delivery_carrier_id = fields.Many2one('delivery.carrier', company_dependent=False, string="Delivery Method", help="Default delivery method used in sales orders.")

    
class SaleOrderSettings(models.Model):
    _name = 'sale.order.settings'

    name = fields.Char('Nombre')
    carga_bultos = fields.Boolean(string="Carga por bultos", default=True)
    carga_unidades = fields.Boolean(string="Carga por unidades")
    activo = fields.Boolean("Activo", default=False)

    @api.onchange('carga_bultos')
    def _onchange_carga_bultos(self):
        for record in self:
            if record.carga_bultos:
                record.carga_unidades = False

    @api.onchange('carga_unidades')
    def _onchange_carga_unidades(self):
        for record in self:
            if record.carga_unidades:
                record.carga_bultos = False


class ProductPricelist(models.Model):
    _inherit = "product.pricelist"
    
    is_default = fields.Boolean(
        string="Lista por defecto",
        default=False,
        copy=False,
        index=True,
        help="Si está marcada, será la lista de precios por defecto."
    )
    
    list_default_b = fields.Boolean(
        string="Lista por defecto B",
        default=False,
        copy=False,
        index=True,
        help="Si está marcada, será la lista de precios por defecto B."
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        to_enforce = records.filtered('is_default')
        is_default_b = records.filtered('list_default_b')
        if is_default_b:
            is_default_b._clear_others_default_b()
        if to_enforce:
            to_enforce._clear_others_default()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_default'):
            self.filtered('is_default')._clear_others_default()
        if vals.get('list_default_b'):
            self.filtered('list_default_b')._clear_others_default_b()
        return res

    def _clear_others_default(self):
        if self.env.context.get('pricelist_toggle_guard'):
            return
        others = self.sudo().search([
            ('is_default', '=', True),
            ('id', 'not in', self.ids),
        ])
        if others:
            others.with_context(pricelist_toggle_guard=True).write({'is_default': False})

    def _clear_others_default_b(self):
        if self.env.context.get('pricelist_toggle_guard_b'):
            return
        others = self.sudo().search([
            ('list_default_b', '=', True),
            ('id', 'not in', self.ids),
        ])
        if others:
            others.with_context(pricelist_toggle_guard_b=True).write({'list_default_b': False})