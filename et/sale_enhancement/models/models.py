from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict
from odoo.tools import float_round, float_compare  # Importa float_round si lo necesitas
# from odoo.tools import float_compare  # Elimina esta línea si no usas float_compare
import math 
import logging
_logger = logging.getLogger(__name__)

class SaleOrderInherit(models.Model):
    _inherit = 'sale.order'

    RUBRO_COMPANY_MAPPING = {
        'JUGUETES': 3,                  #BECHAR SRL
        'CARPAS': 3,                    #BECHAR SRL
        'RODADOS INFANTILES': 3,        #BECHAR SRL
        'PISTOLAS DE AGUA': 4,          #FUN TOYS SRL
        'INFLABLES': 4,                 #FUN TOYS SRL
        'PELOTAS': 4,                   #FUN TOYS SRL
        'VEHICULOS A BATERIA': 4,       #FUN TOYS SRL
        'RODADOS': 2,                   #SEBIGUS SRL
        'MAQUILLAJE': 2,                #SEBIGUS SRL
        'CABALLITOS SALTARINES': 2,     #SEBIGUS SRL
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
    company_default = fields.Many2one("res.company", string="Compañía por Defecto", help="Seleccionar la compañía bajo la cual se creará el pedido de venta.")
    partner_tag_ids = fields.Many2many(
        'res.partner.category',
        string='Etiq. del Cliente',
        compute='_compute_partner_tags',
        store=True,
        readonly=True,
    )
    is_marketing = fields.Boolean(string="Venta de Marketing", default=False)


    def pasar_a_tipo1_seb(self):
        for record in self:
            tipo = self.env['condicion.venta'].browse(6)
            record.condicion_m2m = tipo.id

            if record.state == 'sale':
                x = True
                record.state = 'draft'
                record.order_line.state = 'draft'

            
            for line in record.order_line:
                line.tax_id = False                
                line.company_id = 2
                tax_iva = self.env['account.tax'].search([('description', '=', 'IVA 21%'), ('company_id', '=', 2), ('type_tax_use', '=', 'sale')], limit=1)
                tax_percep = self.env['account.tax'].search([('description', '=', 'Perc IIBB CABA A'), ('company_id', '=', 2), ('type_tax_use', '=', 'sale')], limit=1)
                line.tax_id = tax_iva | tax_percep

            record.write({
                'company_id': 2,
                'warehouse_id': 2,
            })

            if x:
                record.state = 'sale'
                record.order_line.state = 'sale'

    def pasar_a_tipo1_bech(self):
        for record in self:
            tipo = self.env['condicion.venta'].browse(6)
            record.condicion_m2m = tipo.id

            if record.state == 'sale':
                x = True
                record.state = 'draft'
                record.order_line.state = 'draft'

            
            for line in record.order_line:
                line.tax_id = False                
                line.company_id = 3
                tax_iva = self.env['account.tax'].search([('description', '=', 'IVA 21%'), ('company_id', '=', 3), ('type_tax_use', '=', 'sale')], limit=1)
                tax_percep = self.env['account.tax'].search([('description', '=', 'Perc IIBB CABA A'), ('company_id', '=', 3), ('type_tax_use', '=', 'sale')], limit=1)
                line.tax_id = tax_iva | tax_percep

            record.write({
                'company_id': 3,
                'warehouse_id': 3,
            })

            if x:
                record.state = 'sale'
                record.order_line.state = 'sale'

    def pasar_a_tipo1_fun(self):
        for record in self:
            tipo = self.env['condicion.venta'].browse(6)
            record.condicion_m2m = tipo.id

            if record.state == 'sale':
                x = True
                record.state = 'draft'
                record.order_line.state = 'draft'

            
            for line in record.order_line:
                line.tax_id = False                
                line.company_id = 4
                tax_iva = self.env['account.tax'].search([('description', '=', 'IVA 21%'), ('company_id', '=', 4), ('type_tax_use', '=', 'sale')], limit=1)
                tax_percep = self.env['account.tax'].search([('description', '=', 'Perc IIBB CABA A'), ('company_id', '=', 4), ('type_tax_use', '=', 'sale')], limit=1)
                line.tax_id = tax_iva | tax_percep

            record.write({
                'company_id': 4,
                'warehouse_id': 4,
            })

            if x:
                record.state = 'sale'
                record.order_line.state = 'sale'

    @api.depends('partner_id', 'partner_id.category_id')
    def _compute_partner_tags(self):
        for order in self:
            if order.partner_id:
                order.partner_tag_ids = order.partner_id.category_id
            else:
                order.partner_tag_ids = False

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
            if record.pricelist_id:
                if record.is_marketing and not record.pricelist_id.is_marketing:
                    raise UserError("La lista de precios seleccionada no corresponde a Marketing.")
                record.update_lines_prices()

    @api.onchange('condicion_m2m')
    def _onchange_condicion_m2m(self):
        for record in self:
            if record.is_marketing:
                pricelist = self.env['product.pricelist'].search([('is_marketing','=', True)])
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
                    raise UserError("No se encontró precio de lista para Marketing")
            elif record.condicion_m2m.name == 'TIPO 3':
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
                    raise UserError("No se encontró precio de lista para Producción B")
            else:
                pricelist = self.env['product.pricelist'].search([('is_default','=', True)])
                if pricelist:
                    record.pricelist_id = pricelist.id
                else:
                    raise UserError("No se encontró precio de lista por defecto")

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

    @api.onchange('company_default', 'order_line')
    def _onchange_company_default_or_lines(self):
        for order in self:
            if order.state not in ('draft',):
                continue
            if order.company_default:
                order._apply_company_default(order.company_default)
            elif order.is_marketing:
                continue
            elif order.condicion_m2m.name == 'TIPO 3' or order.special_price:
                continue
            else:
                order._apply_company_from_rubros()

    def _apply_company_default(self, company):
        if not company:
            return
        wh = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        if not wh:
            raise UserError(_("No tiene asignada la compañía %s, verifique su listado de Compañias.") % company.display_name)
        self.company_id = company.id
        self.warehouse_id = wh.id

    def _apply_company_from_rubros(self):
        for order in self:
            company_sets = []
            by_set = defaultdict(list)
            
            for line in order.order_line:
                product = line.product_id
                if not product:
                    continue
                if getattr(product, 'company_ids', False) and product.company_ids:
                    comp_ids = set(product.company_ids.ids)
                elif product.company_id:
                    comp_ids = {product.company_id.id}
                else:
                    comp_ids = set()
                if comp_ids:
                    company_sets.append(comp_ids)
                if getattr(product, 'company_ids', False) and product.company_ids:
                    ids_tuple = tuple(sorted(product.company_ids.ids))
                elif product.company_id:
                    ids_tuple = (product.company_id.id,)
                else:
                    ids_tuple = tuple()
                code = product.default_code or product.display_name or ''
                by_set[ids_tuple].append(code)
            if not company_sets:
                continue
            common = set.intersection(*company_sets)

            if not common:
                def set_label(ids_tuple):
                    if not ids_tuple:
                        return _('(compartido / sin compañía)')
                    comps = self.env['res.company'].browse(list(ids_tuple))
                    return ', '.join(comps.mapped('name'))
                lines = "\n".join(
                    "---- ({codes} → {companies})".format(
                        codes=", ".join(sorted(codes)),
                        companies=set_label(ids_tuple),
                    )
                    for ids_tuple, codes in sorted(by_set.items(), key=lambda it: (len(it[0]) or 0, it[0]))
                )
                raise UserError(_(
                    "Las líneas del pedido no comparten ninguna compañía en común.\n%s\n\n"
                    "Revisá las compañías de los productos, o seleccioná manualmente una 'Compañía por Defecto'."
                ) % lines)
            if order.company_id and order.company_id.id in common:
                target_company_id = order.company_id.id
            else:
                target_company_id = min(common)
            company = self.env['res.company'].browse(target_company_id)
            wh = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
            if not wh:
                raise UserError(_("No tiene asignada la compañía %s, verifique su listado de Compañias.") % company.display_name)
            order.company_id = company.id
            order.warehouse_id = wh.id

    @api.model
    def create(self, vals):
        #self.check_partner_origin()
        cond_model = self.env['condicion.venta']
        cond_name = cond_model.browse(vals.get('condicion_m2m')).name or ''
        force_company = (cond_name.strip().upper() == 'TIPO 3')
        company_produccion_b = self.env['res.company'].browse(1)
        current_company_id = vals.get('company_id')
        company_default = vals.get('company_default', False)
        is_marketing = vals.get('is_marketing')

        if company_default:
            company_default = self.env['res.company'].search([('id', '=', company_default)], limit=1)
            if not company_default:
                raise UserError(_("No se encontró la compañía con nombre %s.") % vals.get('company_default'))
            wh = self.env['stock.warehouse'].search([('company_id', '=', company_default.id)], limit=1)
            if not wh:
                raise UserError(_("No tiene asignada la compañía %s, verifique su listado de Compañias.") % company_default.display_name )

            vals = dict(vals)
            vals['company_id'] = company_default.id    
            vals['warehouse_id'] = wh.id
            self.with_context(allowed_company_ids=[company_produccion_b.id]).with_company(company_produccion_b)
            order = super().create(vals)    
        elif is_marketing:
            wh = self.env['stock.warehouse'].search([('company_id', '=', company_produccion_b.id)], limit=1)
            if not wh:
                raise UserError(_("No tiene asignada la compañía %s, verifique su listado de Compañias.") % company_produccion_b.display_name)
            pricelist = self.env['product.pricelist'].search([('is_marketing','=', True)], limit=1)
            #setear condicion de venta TIPO 3
            vals['condicion_m2m'] = self.env['condicion.venta'].search([('name', '=', 'TIPO 3')], limit=1).id
            if pricelist:
                vals = dict(vals)
                vals['pricelist_id'] = pricelist.id
                vals['company_id'] = company_produccion_b.id
                vals['warehouse_id'] = wh.id
                self.with_context(allowed_company_ids=[company_produccion_b.id]).with_company(company_produccion_b)
                order = super().create(vals)    
            else: 
                raise UserError("No se encontró precio de lista para Marketing")
        else:
            #Ajustar compañía si es TIPO 3
            if force_company and current_company_id != company_produccion_b.id:
                wh = self.env['stock.warehouse'].search([('company_id', '=', company_produccion_b.id)], limit=1)
                if not wh:
                    raise UserError(_("No tiene asignada la compañía %s, verifique su listado de Compañias.") % company_produccion_b.display_name)

                vals = dict(vals)  # copiar para no mutar
                vals['company_id'] = company_produccion_b.id
                vals['warehouse_id'] = wh.id

                # Crear bajo el contexto/compañía destino para evitar conflictos multi-company
                self.with_context(allowed_company_ids=[company_produccion_b.id]).with_company(company_produccion_b)
                order = super().create(vals)    
            # Si no es TIPO 3, inferir compañía por productos
            else:
                line_cmds = vals.get('order_line') or []
                product_ids = set()

                for cmd in line_cmds:
                    if not isinstance(cmd, (list, tuple)) or not cmd:
                        continue
                    op = cmd[0]
                    if op == 0 and len(cmd) >= 3:
                        pid = (cmd[2] or {}).get('product_id')
                        if pid:
                            product_ids.add(pid)
                    elif op in (1, 4) and len(cmd) >= 2:
                        line = self.env['sale.order.line'].browse(cmd[1])
                        if line.exists():
                            product_ids.add(line.product_id.id)
                    elif op == 6 and len(cmd) >= 3:
                        for line_id in (cmd[2] or []):
                            line = self.env['sale.order.line'].browse(line_id)
                            if line.exists():
                                product_ids.add(line.product_id.id)
                # Si hay productos en las líneas, infiero compañía
                if product_ids:
                    prods = self.env['product.product'].browse(list(product_ids))
                    detailed = []
                    company_sets = []

                    for p in prods:
                        comp_ids = set()
                        if getattr(p, 'company_ids', False) and p.company_ids:
                            comp_ids = set(p.company_ids.ids)
                            comp_names = ', '.join(p.company_ids.mapped('name'))
                        elif p.company_id:
                            comp_ids = {p.company_id.id}
                            comp_names = p.company_id.display_name
                        else:
                            # compartido ⇒ no restringe
                            comp_names = _('(compartido)')
                        if comp_ids:
                            company_sets.append(comp_ids)
                        detailed.append((p.default_code or p.display_name, comp_names))

                    if company_sets:
                        # intersección de TODAS las compañías de los productos con restricción
                        common = set.intersection(*company_sets)
                        if not common:
                            # Agrupar por conjunto de compañías del producto
                            by_set = defaultdict(list)
                            for p in prods:
                                code = p.default_code or p.display_name
                                if getattr(p, 'company_ids', False) and p.company_ids:
                                    ids_tuple = tuple(sorted(p.company_ids.ids))
                                elif p.company_id:
                                    ids_tuple = (p.company_id.id,)
                                else:
                                    ids_tuple = tuple()
                                by_set[ids_tuple].append(code)

                            def set_label(ids_tuple):
                                if not ids_tuple:
                                    return _('(compartido)')
                                comps = self.env['res.company'].browse(list(ids_tuple))
                                return ', '.join(comps.mapped('name'))
                            # Construir líneas agrupadas: "códigos → compañías"
                            lines = "\n".join(
                                f"---- ({', '.join(sorted(codes))} → {set_label(ids_tuple)})"
                                for ids_tuple, codes in sorted(by_set.items(), key=lambda it: (len(it[0]) or 0, it[0]))
                            )
                            raise UserError(_(
                                "No se puede crear el pedido: las líneas no comparten una compañía común.\n%s\n"
                                "Asegurate de que todos los productos compartan al menos una misma compañía."
                            ) % lines)
                        current_company_id = vals.get('company_id')
                        if current_company_id in common:
                            target_company_id = current_company_id
                        elif 1 in common:
                            target_company_id = 1
                        else:
                            target_company_id = min(common)
                        company_name_id = self.env['res.company'].browse(target_company_id)
                        if vals.get('company_id') != target_company_id:
                            wh = self.env['stock.warehouse'].search([('company_id', '=', target_company_id)], limit=1)
                            if not wh:
                                raise UserError(_("No tiene asignada la compañía %s, verifique su listado de Compañias.") % company_name_id.display_name)
                            vals = dict(vals)
                            vals['company_id'] = target_company_id
                            vals['warehouse_id'] = wh.id
                            target_company = self.env['res.company'].browse(target_company_id)
                            self = self.with_context(allowed_company_ids=[target_company_id]).with_company(target_company)
                order = super(SaleOrderInherit, self).create(vals)
                if order.order_line:
                    order.order_line.filtered(lambda l: l.company_id != order.company_id).write({
                        'company_id': order.company_id.id
                    })
                    bad_lines = order.order_line.filtered(
                        lambda l: (
                            hasattr(l.product_id, 'company_ids') and l.product_id.company_ids and order.company_id not in l.product_id.company_ids
                        ) or (
                            l.product_id.company_id and l.product_id.company_id != order.company_id
                        )
                    )
                    if bad_lines:
                        names = ", ".join(bad_lines.mapped('product_id.display_name')[:5])
                        raise UserError(_(
                            "Hay líneas con productos que no pertenecen a la compañía del pedido (%s): %s"
                        ) % (order.company_id.display_name, names + ('...' if len(bad_lines) > 5 else '')))
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
            if record.is_marketing:
                pricelist = self.env['product.pricelist'].search([('is_marketing','=', True)], limit=1)
                if pricelist:
                    record.pricelist_id = pricelist.id
            elif record.condicion_m2m.name == 'TIPO 3':
                pricelist = self.env['product.pricelist'].search([('list_default_b','=', True)], limit=1)
                if pricelist:
                    record.pricelist_id = pricelist.id
            else:
                pricelist = self.env['product.pricelist'].search([('is_default','=', True)], limit=1)
                if pricelist:
                    record.pricelist_id = pricelist.id

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
    
    
    def _get_tax_totals_for_lines(self, lines):
        """
        Devuelve el dict tax_totals pero solo para 'lines'.
        Reutiliza la misma lógica del core.
        """
        self.ensure_one()
        currency = self.currency_id
        tax_totals = self.env['account.tax']._prepare_tax_totals(
            base_lines=lines,
            currency=currency,
            company=self.company_id,
            partner=self.partner_id,
        )
        return tax_totals
    
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
            if not record.is_available:
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
    
    is_marketing = fields.Boolean(
        string="Lista de Marketing",
        default=False,
        copy=False,
        index=True,
        help="Si está marcada, será la lista de precios de marketing."
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        to_enforce = records.filtered('is_default')
        is_default_b = records.filtered('list_default_b')
        is_marketing = records.filtered('is_marketing')
        if is_default_b:
            is_default_b._clear_others_default_b()
        if to_enforce:
            to_enforce._clear_others_default()
        if is_marketing:
            is_marketing._clear_others_marketing()
        return records

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_default'):
            self.filtered('is_default')._clear_others_default()
        if vals.get('list_default_b'):
            self.filtered('list_default_b')._clear_others_default_b()
        if vals.get('is_marketing'):
            self.filtered('is_marketing')._clear_others_marketing()
        return res

    def _clear_others_marketing(self):
        if self.env.context.get('pricelist_toggle_guard_marketing'):
            return
        others = self.sudo().search([
            ('is_marketing', '=', True),
            ('id', 'not in', self.ids),
        ])
        if others:
            others.with_context(pricelist_toggle_guard_marketing=True).write({'is_marketing': False})

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