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
        'RODADOS': 2,
        'MAQUILLAJE': 2,
        'PELOTAS': 4,
        'CABALLITOS SALTARINES': 4,
        'VEHICULOS A BATERIA': 4,
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

    ### ONCHANGE

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for record in self:

            if record.partner_id:
                record.check_price_list()


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
                pricelist = self.env['product.pricelist'].search([('id','=',46)])

                if pricelist:
                    record.pricelist_id = pricelist
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

        records = super().create(vals)


        for record in records:
            company_produccionb_id = 1
            if record.company_id.id != company_produccionb_id and record.condicion_m2m.name == 'TIPO 3':
                record.write({'company_id': company_produccionb_id})
                for line in record.order_line:
                    if line.company_id.id != company_produccionb_id:
                        line.write({'company_id': company_produccionb_id})
                record.message_post(body=_("Compañía cambiada a %s en el pedido y todas sus líneas durante la creación.") % record.company_id.name)
                    
            
            record.check_order()
            if not record.message_ids:
                record.message_post(body=_("Orden de venta creada."))
        return records

    def action_confirm(self):
        res = super().action_confirm()
        for record in self:
            company_letter = record._get_company_letter(record)

            record.name = f"{record.name} - {company_letter}"

            for picking in record.picking_ids:
                picking.origin = record.name

            if company_letter == 'P':               
                pricelist = self.env['product.pricelist'].search([('id','=',46)])

                if pricelist:
                    record.pricelist_id = pricelist
                    discounts = {}
                    for line in record.order_line:
                        discounts[line.id] = line.discount
                        
                    record.update_prices()
                    
                    for line in record.order_line:
                        if line.id in discounts:
                            line.discount = discounts[line.id]
                else: 
                    raise UserError("No se encontró precio de lista con ID 46")
            

            # STOCK ERP

            vals_list = []
            for line in record.order_line:
                vals = {}
                stock_erp = self.env['stock.erp'].search([('product_id', '=', line.product_id.id)], limit=1)
                if stock_erp:
                    vals['stock_erp'] = stock_erp.id
                else:
                    raise UserError(f'El producto [{line.product_id.default_code}]{line.product_id.name} no se encuentra en el listado de Stock. Avise al administrador.')

                if record.picking_ids:
                    vals['picking_id'] = record.picking_ids[0].id
                vals['sale_id'] = record.id
                vals['sale_line_id'] = line.id
                vals['product_id'] = line.product_id.id
                vals['quantity'] = line.product_uom_qty
                vals['uxb'] = line.product_packaging_id.qty or ''
                vals['bultos'] = line.product_packaging_qty

                vals_list.append(vals)
            
            self.env['stock.moves.erp'].create(vals_list)

        return res

    def update_prices(self):
        self.ensure_one()
        for line in self._get_update_prices_lines():
            line.product_uom_change()
            line.discount = 0
            line._onchange_discount()
        self.show_update_pricelist = False


    ### CUSTOM

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
            if record.condicion_m2m.name == 'TIPO 3':
                pricelist = self.env['product.pricelist'].browse(35)
                if pricelist:
                    record.pricelist_id = pricelist


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

    stock_state = fields.Selection(string='Disponibilidad', selection=[('available', 'Disponible'), ('unavailable', 'No Disponible')], compute="_compute_stock_state")
    disponible_unidades = fields.Integer('Disponible')
    comprometido_unidades = fields.Integer('Comprometido')
    
    def create(self, vals):
        res = super().create(vals)
        for rec in res:
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
             
        return res


    def update_stock_erp(self):
        for record in self:
            stock_erp = self.env['stock.erp'].search([('product_id', '=', record.product_id.id)], limit=1)
            if stock_erp:
                record.disponible_unidades = stock_erp.disponible_unidades
        
    # COMPUTED

    @api.depends('disponible_unidades')
    def _compute_stock_state(self):
        for record in self:
            if record.product_uom_qty <= record.disponible_unidades:
                record.stock_state = 'available'
            else:
                record.stock_state = 'unavailable'


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

    # custom
    # declared_value_type = fields.Selection()

class SaleOrderSplitWizardInherit(models.TransientModel):
    _inherit = 'sale.order.split.wizard'

    percentage = fields.Float(
        string='Porcentaje (%)',
        digits=(10, 2),
        required=True,
        default=lambda self: self._default_percentage()
    )



    def _default_percentage(self):
        sale_order_id = self._context.get('active_id')
        sale_order = self.env['sale.order'].browse(sale_order_id)
        if sale_order and sale_order.condicion_m2m_numeric:
            try:
                return float(sale_order.condicion_m2m_numeric)
            except ValueError:
                raise UserError(_("condicion_m2m_numeric field must be a valid number."))

    def action_split_sale_orders(self):

        original_order = self.env['sale.order'].browse(self._context.get('active_id'))

        if original_order.splitted:
            raise UserError(_("La Orden de Venta original ya está dividida."))

        new_orders = self.env['sale.order']

        company_id_1 = original_order.company_id.id
        company_id_2 = int(self.env['ir.config_parameter'].sudo().get_param('sale_order_split.company_id'))
        company_ids = [company_id_1, company_id_2]

        for company_id in company_ids:
            name = self.env['res.company'].sudo().search([('id','=',company_id)]).name
            new_order_vals = {
                'name': original_order.name + str(" - ") + str(name[0]),
                'partner_id': original_order.partner_id.id,
                'order_line': [],
                'company_id': company_id,
                'sale_order_template_id': original_order.sale_order_template_id.id,
                'pricelist_id': original_order.pricelist_id.id,
                'validity_date': original_order.validity_date,
                'date_order': original_order.date_order,
                'payment_term_id': original_order.payment_term_id.id,
                'picking_policy': original_order.picking_policy,
                'user_id': original_order.user_id.id,
                'splitted': 1,
                'condicion_venta': original_order.condicion_venta,
                'note': original_order.note,
                'internal_notes': original_order.internal_notes,
                'available_condiciones': False,
                'condicion_m2m': original_order.condicion_m2m.id,
                'condicion_m2m_numeric': original_order.condicion_m2m_numeric,
                'state': 'sale',
                'client_order_ref': original_order.company_id.name,
                'special_price': original_order.special_price,
            }
            # _logger.info(f"Nueva SO: {new_order_vals}")

            for line_index, line in enumerate(original_order.order_line):
                quantity = round(line.product_uom_qty * self.percentage / 100)

                # IMPUESTOS DEL PRODUCTO
                # valid_taxes = line.product_id.taxes_id.filtered(lambda tax: tax.company_id.id == company_id)
                valid_taxes = line.tax_id.filtered(lambda tax: tax.company_id.id == company_id)
                # _logger.info(f"Impuestos de línea: {valid_taxes.ids}")

                new_order_line_vals = (0, 0, {
                      'product_id': line.product_id.id,
                      'product_uom_qty': quantity,
                      'product_uom': line.product_uom.id,
                      #'product_packaging_qty': quantity / line.product_packaging_id.qty if line.product_packaging_id else 0,
                      'product_packaging_qty': line.product_packaging_qty,
                      'product_packaging_id': line.product_packaging_id.id,
                      'price_unit': line.price_unit,
                      'tax_id': [(6, 0, valid_taxes.ids)],
                      'discount': line.discount,
                })
                new_order_vals['order_line'].append(new_order_line_vals)
                # _logger.info(f"Valores de nueva línea: {new_order_line_vals}")

            new_order = self.env['sale.order'].create(new_order_vals)
            new_orders += new_order

        for original_line in original_order.order_line:
            original_quantity = original_line.product_uom_qty
            new_quantity = sum(line.product_uom_qty for new_order in new_orders for line in new_order.order_line if line.product_id == original_line.product_id)
            if abs(new_quantity - original_quantity) > 0.01:
                difference = original_quantity - new_quantity

                # POR CASO DE DIFERENCIA MAYOR A CANTIDAD ORIGINAL
                difference = int(-original_quantity if difference < 0 and abs(difference) > original_quantity else difference)

                _logger.info(f"Diferencia: {difference}")

                for new_order in new_orders:
                    for line in new_order.order_line:
                        if line.product_id == original_line.product_id:
                            _logger.info(f"line.product_uom_qty 1 %%%: {line.product_uom_qty}")
                            # VAMOS CON TRY
                            try:
                                line.product_uom_qty += difference
                            except Exception as e:
                                _logger.error(f"Error adjusting quantity for {line.product_id.name}: {e}")
                                continue
                            # line.product_uom_qty += difference
                            _logger.info(f"line.product_uom_qty 2 %%%: {line.product_uom_qty}")
                            break
                    break

        # ESTO NO SIRVE CON EL BOTÓN DE CONFIRMACIÓN, PORQUE PRIMERO CONFIRMA,
        # ENTONCES LUEGO NO PUEDE ELIMINAR: COMENTAMOS LÍNEAS
        # for new_order in new_orders:
        #     for line in new_order.order_line:
        #         if line.product_uom_qty == 0:
        #             new_order.write({'order_line': [(3, line.id)]})

        original_order.action_cancel()
        original_order.toggle_active()

        for new_order in new_orders:
            new_order.write({'origin': original_order.name})

        for new_order in new_orders:
            if new_order.amount_total == 0:
                new_order.action_cancel()
                new_order.unlink()

    
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