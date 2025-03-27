# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.tools.image import image_data_uri
from odoo.addons.portal.controllers import portal

import json


import logging
_logger = logging.getLogger(__name__)

class PedidosOnline(http.Controller):
    @http.route('/sebigus/pedidos-catalogos', auth='user', website=True)
    def catalogos(self, **kw):
        values = {}
        return request.render('sebigus.pedidos_online_catalogos', values)

    @http.route('/sebigus/pedidos', auth='user', website=True)
    def index(self, **kw):
        values = {}
        return request.render('sebigus.pedidos_online', values)

    @http.route('/sebigus/pedidos-enviar', auth='user', website=True)
    def enviar_pedido(self, **kw):
        values = {}
        categoria= kw.get('catalogo')
        so_id= kw.get('so')
        sale_order_obj = request.env['sale.order']
        product_obj = request.env['product.product']
        _logger.info('Usuario: %s' % request.session.uid)
        partner = request.env['res.users'].browse(request.session.uid).partner_id
        _logger.info('Usuario: %s Partner: %s' % (request.session.uid,partner))
        # Busco si el usuario tiene un orden de venta en borrador
        so = sale_order_obj.sudo().search([('state','=','draft'),('partner_id','=',partner.id),('client_order_ref','=',categoria)])
        so = so[0]
        #so = sale_order_obj.sudo().search([('id','=',so_id)])
        _logger.info('Usuario: %s Partner: %s' % (request.session.uid,partner))
        _logger.info('SO %s' % so)
        values['sale_order']  = so
        if so and so.state == 'draft':
           so.sudo().action_confirm()
        order_sudo = so
        download = False
        #return portal.CustomerPortal._show_report(self,model=order_sudo, report_type='html', report_ref='sebigus.action_report_saleorder', download=download)
        return request.render('sebigus.report_saleorder_confirm', values)
        #return request.render('sale.sale_order_portal_content', values)

    @http.route('/sebigus/pedidos/cargar_unidades', auth='user', website=True)
    def cargar_unidades(self, **kw):
        codigo= kw.get('codigo')
        cantidad= kw.get('cantidad')
        categoria= kw.get('catalogo')
        stock= kw.get('stock')
        sale_order_obj = request.env['sale.order']
        product_obj = request.env['product.product']
        product_id = product_obj.search([('default_code','=',codigo)])
        _logger.info('Producto: %s %s' % ( product_id, cantidad) )
        _logger.info('Usuario: %s' % request.session.uid)
        partner = request.env['res.users'].browse(request.session.uid).partner_id
        _logger.info('Usuario: %s Partner: %s' % (request.session.uid,partner))
        # Busco si el usuario tiene un orden de venta en borrador
        sale_order_line_obj = request.env['sale.order.line']
        so = sale_order_obj.search([('state','=','draft'),('partner_id','=',partner.id),('client_order_ref','=',categoria)])
        if not so:
            # Creo una nueva Sale order
            vars={}
            vars['partner_id'] = partner.id
            vars['client_order_ref'] = categoria
            vars['state'] = 'draft'
            vars['team_id'] = 5
            so = sale_order_obj.sudo().create(vars) 
        so = so[0]
        _logger.info('SO %s' % so.id)
        sale_order_line_obj.search([('order_id','=',so.id),('product_id', '=' , product_id.id)]).sudo().unlink()
        if float(cantidad) > 0:
            bultos  = float(cantidad)  / product_id.uom_po_id.ratio
            if float(stock) < 0:
                demanda = float(cantidad)
                cantidad = 0
            else:
                cantidad = float(cantidad)
                demanda = 0
                
            vals = {
                        'order_id': so.id,
                        'product_id': product_id.id,
                        'product_uom_qty': float(cantidad),
                        'product_demand_qty': float(demanda),
                        'product_uom': product_id.uom_id.id,
                        'name': product_id.name,
                        'product_packaging_qty': bultos,
                    }
            for pkg_id in product_id.packaging_ids:
                if product_id.uom_po_id.ratio == pkg_id.qty:
                    vals['product_packaging_id'] = pkg_id.id
            _logger.info('Producto: %s SO: %s' % (vals,so))
            new = sale_order_line_obj.sudo().create(vals)
            new._compute_name()
        return None

    @http.route('/sebigus/pedidos/productos', auth='user', website=True)
    def productos(self, **kw):
        dt = DataTablesRequest(kw)
        _logger.info('SEARCH %s' % dt.search_value)
        _logger.info('SEARCH %s' % dt.categoria)
        _logger.info('SEARCH %s' % dt.start)
        _logger.info('SEARCH %s' % dt.length)
        unidades_pedidas ={}
        # Busco si el clientes tiene un SO en draft y cargo las unidades 
        partner = request.env['res.users'].browse(request.session.uid).partner_id
        sale_order_obj = request.env['sale.order']
        so = sale_order_obj.search([('state','=','draft'),('partner_id','=',partner.id),('client_order_ref','=',dt.categoria)],limit=1)
        _logger.info('SO %s' % so)
        if so:
            for line in so.order_line:
                if line.product_uom_qty > 0:
                    unidades_pedidas[line.product_id.default_code] = line.product_packaging_qty 
                if line.product_demand_qty > 0:
                    unidades_pedidas[line.product_id.default_code] = line.product_packaging_qty  * -1
        if 'SUGERIDOS' in dt.search_value:
            codigo = dt.search_value.split('_')[1]
            data=self.sugeridos(codigo,unidades_pedidas,so)
            _logger.info(data)
            if len(data) > 3:
                return json.dumps(dict(data=data,recordsTotal=0,recordsFiltered=0))
            else:
                dt.search_value = None
        #_logger.info('TIEMPO Inicio %s Search' % len(dt.search_value))
        tot_reg = len(request.env['product.template'].sudo().search([('product_brand_id','=', int(dt.categoria) )]))
        prods = {}
        if dt.search_value and len(dt.search_value) > 4:
            _logger.info('TIEMPO Inicio %s Search' % dt.search_value)
            #tot_search = len(request.env['product.template'].sudo().search([('product_brand_id','=', int(dt.categoria)),'|',('name','like',dt.search_value),('default_code','like',dt.search_value)]))
            prod = request.env['product.template'].sudo().search([('product_brand_id','=', int(dt.categoria)),'|',('name','like',dt.search_value),('default_code','like',dt.search_value)],limit=dt.length,offset=dt.start,order='default_code')
        else:
            #tot_search = tot_reg
            #prod = request.env['product.template'].sudo().search([('id','>',0)],limit=dt.length,offset=dt.start,order='id')
            prod = request.env['product.template'].sudo().search([('id','>',0),('product_brand_id','=', int(dt.categoria))])
        tot_search = len(prod)
        _logger.info('TIEMPO Fin %s' % tot_search)

        for p in prod:
            try:
                prods['%-20s_%s' % (p.public_categ_ids[0].name.strip(),p.default_code)] = p
            except:
                continue
        _logger.info('TIEMPO Cat')
        stock_actual={}
        quants = request.env['stock.quant'].sudo().search([('location_id','=',8)])
        for q in quants:
            if q.product_id.default_code in unidades_pedidas:
                stock_actual[q.product_id.id]= q[0].available_quantity  - unidades_pedidas[q.product_id.default_code] * q.product_id.uom_po_id.ratio
            else:
                stock_actual[q.product_id.id]= q[0].available_quantity 
            
        _logger.info('TIEMPO stock')
        data = []
        data_tmp = []
        categoria = 0
        pos = 0
        for pp in sorted(prods)[dt.start:]:
        #for pp in sorted(prods):
            if dt.length > 0:
                pos += 1
                if pos == dt.length:
                    break
            p=prods[pp]
            if p.public_categ_ids and p.public_categ_ids[0] != categoria:
                _logger.info('CATEGORIA %s %s' %( categoria,pp))
                try:
                    categoria = p.public_categ_ids[0]
                except:
                    continue
                # Cuando cambio de categoria ordeno por precio 
                if len(data_tmp) > 0:
                    newlist = sorted(data_tmp, key=lambda d: d['Precio']) 
                    data_tmp = []
                    data.append(titulos_seccion)
                    data = data  + newlist
                det = {}
                det['DT_RowId'] = 'categoria'
                if categoria.image_1920:
                    det['Imagen'] = "<img loading='lazy' src=/web/image/product.public.category/%s/image_1920  width='900px' alt=%s/>" % (p.public_categ_ids[0].id,p.public_categ_ids[0].name)
                else:
                    det['Imagen'] = "<h5>%s</h5>" % p.public_categ_ids[0].name
                det['Codigo'] = "  "
                det['Descripcion'] = " "
                det['Dimensiones'] = " "
                det['Bulto'] = " "
                det['Precio'] = " "  
                det['Pedido'] =  " "
                det['Unidades_Pedidas'] = p.public_categ_ids[0].name
                det['Stock'] = " "
                det['Stock_Sugeridos'] = " "
                titulos_seccion = det
                #data.append(det)
            det = {}
            det['DT_RowId'] = 'row_%s' % p.default_code
            det['Imagen'] = "<img loading='lazy' src=/web/image/product.template/%s/image_128 width='50px' />" % p.id
            det['Codigo'] = p.default_code
            det['Descripcion'] = p.name
            det['Dimensiones'] = p.description_sale if p.description_sale else ' '
            det['Bulto'] = "<span id=uxb_%s>%d</span>" % (p.default_code, p.uom_po_id.ratio) 
            det['Precio'] = p.list_price 
            #quants = request.env['stock.quant'].sudo().search([('product_id','=',p.id),('location_id','=',8)])
            quants = stock_actual[p.id] if p.id in stock_actual else None
            bultos = ''
            cant = ''
            det['Pedido'] = "<input type='number' min=0 step='0.25' id=%s style='width: 100px;'  onChange=cantidad_pedida(%s) onfocus=update_codigo(%s) value=%s />" % (p.default_code,p.default_code,p.default_code,bultos) # ,p.default_code)
            if p.default_code in unidades_pedidas:
                if unidades_pedidas[p.default_code] > 0:
                    bultos = unidades_pedidas[p.default_code]
                    cant  = int(bultos  * p.uom_po_id.ratio)
                    det['Pedido'] = "<input type='number' min=0 step='0.25' id=%s style='width: 100px;'  onChange=cantidad_pedida(%s) onfocus=update_codigo(%s) value=%s />" % (p.default_code,p.default_code,p.default_code,bultos) # ,p.default_code)
                else:
                    det['Pedido'] = "<input type='number' min=0  max=0 step='0' id=%s style='width: 100px;'  value=%s />" % (p.default_code,bultos) # ,p.default_code)
                    cant='Agotado'
            det['Unidades_Pedidas'] = "<span id=tot_%s>%s</span>" % (p.default_code,cant)
            if quants and quants > 0:
                det['Stock'] = "<span id=stock_%s>%s</span>" % (p.default_code,quants)
            else:
                det['Stock'] = "<span id=stock_%s>%s</span>" % (p.default_code,self.sugeridos_stock(p.default_code) * -1 )
            if p.list_price > 1:
                data_tmp.append(det)
        if len(data_tmp) > 0:
            newlist = sorted(data_tmp, key=lambda d: d['Precio']) 
            data.append(titulos_seccion)
            data = data  + newlist
        _logger.info('TIEMPO Tabla')
        return json.dumps(dict(data=data,recordsTotal=tot_reg,recordsFiltered=tot_search))
    
    @http.route('/sebigus/pedidos/detalle', auth='user', website=True)
    def producto(self, **kw):
        codigo= kw.get('codigo')
        if codigo:
            producto = request.env['product.template'].sudo().search([('default_code','=',codigo)])
        values = {'producto':producto}
        return request.render('sebigus.producto_detalle', values)

    def sugeridos_stock(self,codigo):
        prod = request.env['product.template'].sudo().search([('default_code','=',codigo)])
        stock = 0
        for p in prod.alternative_product_ids:
            quants = request.env['stock.quant'].sudo().search([('product_id','=',p.id),('location_id','=',8)])
            if quants and quants[0].available_quantity > 0 and p.default_code != codigo:
                stock += quants[0].available_quantity
        return stock

    def sugeridos(self,codigo,unidades_pedidas={},so=None):
        data=[]
        if codigo:
            prod = request.env['product.template'].sudo().search([('default_code','=',codigo)])
            det = {}
            det['DT_RowId'] = 'row_%s' % prod.default_code
            det['Imagen'] = "<img loading='lazy' src=/web/image/product.template/%s/image_128 width='50px' />" % prod.id
            det['Codigo'] = prod.default_code
            det['Descripcion'] = prod.name
            det['Dimensiones'] = prod.description_sale if prod.description_sale else ' '
            det['Bulto'] = "<span id=uxb_%s>%d</span>" % (prod.default_code, prod.uom_po_id.ratio) 
            det['Precio'] = prod.list_price 
            det['Pedido'] =  " "
            det['Unidades_Pedidas'] = " "
            det['Stock'] = 0 
            data.append(det)
            detc = {}
            detc['DT_RowId'] = 'categoria'
            detc['Imagen'] = "<h5>No tenemos stock de este producto, mirá opciones similares que te recomendamos</h5> <button class='btn btn-default btn-primary' onclick=continuar(%s)>Continuar Comprando</button>"  % prod.default_code
            detc['Codigo'] = "  "
            detc['Descripcion'] = " "
            detc['Dimensiones'] = " "
            detc['Bulto'] = " "
            detc['Precio'] = " "  
            detc['Pedido'] =  " "
            detc['Unidades_Pedidas'] = " "
            detc['Stock'] = " "
            data.append(detc)
            for p in prod.alternative_product_ids:
                quants = request.env['stock.quant'].sudo().search([('product_id','=',p.id),('location_id','=',8)])
                if quants and quants[0].available_quantity > 0 and p.default_code != codigo:
                    det = {}
                    det['DT_RowId'] = 'row_%s' % p.default_code
                    det['Imagen'] = "<img loading='lazy' src=/web/image/product.template/%s/image_128 width='50px' />" % p.id
                    det['Codigo'] = p.default_code
                    det['Descripcion'] = p.name
                    det['Dimensiones'] = p.description_sale if p.description_sale else ' '
                    det['Bulto'] = "<span id=uxb_%s>%d</span>" % (p.default_code, p.uom_po_id.ratio) 
                    det['Precio'] = p.list_price 
                    det['Pedido'] = "<input type='number' min=0 step='0.25' id=%s style='width: 100px;'  onChange=cantidad_pedida(%s) onfocus=update_codigo(%s) />" % (p.default_code,p.default_code,p.default_code) # ,p.default_code)
                    if p.default_code in unidades_pedidas:
                        bultos = unidades_pedidas[p.default_code]
                        cant  = int(bultos  * p.uom_po_id.ratio)
                    else:
                        bultos = ''
                        cant = ''
                    det['Pedido'] = "<input type='number' min=0 step='0.25' id=%s style='width: 100px;'  onChange=cantidad_pedida(%s) onfocus=update_codigo(%s) value=%s />" % (p.default_code,p.default_code,p.default_code,bultos) # ,p.default_code)
                    det['Unidades_Pedidas'] = "<span id=tot_%s>%s</span>" % (p.default_code,cant)
                    det['Stock'] = "<span id=stock_%s>%s</span>" % (p.default_code,quants[0].available_quantity)
                    data.append(det)
            detc2 = detc.copy()
            detc2['Imagen'] = "<button class='btn btn-default btn-primary' onclick=continuar(%s)>Continuar Comprando</button>"  % prod.default_code
            data.append(detc2)
        return data

class DataTablesRequest:
    def __init__(self, get_vars):
        """
        the data request coming from a datatables.net ajax call

        :param get_vars: vars supplied by datatables.net
        """
        self.draw = None
        self.start = 0
        self.length = 15
        self.search_value = ' '
        self.search_regex = None
        self.columns = dict()
        self.orderby = dict()
        self.dal_orderby = []
        self.categoria = None

        self.get_vars = get_vars

        self.parse()

    def parse(self):
        """
        parse all the args we need from datatables.net into instance variables

        :return:
        """
        for x in self.get_vars:
            value = self.get_vars[x]
            if x == "start":
                try:
                    self.start = int(value)
                except:
                    self.start = 0
            elif x == "draw":
                self.draw = value
            elif x == "length":
                self.length = int(value) if int(value) > 0 else 0
            elif x == "search[value]":
                self.search_value = value.upper()
            elif x == "search[regex]":
                self.search_regex = value
            elif x == "categoria":
                self.categoria = value
            elif x[:7] == "columns":
                column = dict()

                #  get start and end positions of attributes
                column_number_start = x.find("[")
                column_number_end = x.find("]", column_number_start)
                column_attribute_start = column_number_end + 2
                column_attribute_end = x.find("]", column_attribute_start)
                column_sub_attribute_start = x.find("[", column_attribute_end)

                column_number = int(x[column_number_start + 1 : column_number_end])

                if column_number in self.columns:
                    column = self.columns[column_number]

                #  get the attribute name and value
                column_attribute = x[column_attribute_start:column_attribute_end]
                column_sub_attribute = ""
                if column_sub_attribute_start and column_sub_attribute_start > 0:
                    column_sub_attribute = x[column_sub_attribute_start + 1 : -1]

                column["column_number"] = column_number
                if column_sub_attribute:
                    column_attribute += f"_{column_sub_attribute}"

                column[column_attribute] = value

                self.columns[column_number] = column
            elif x[:5] == "order":
                orderby = dict()

                #  get start and end positions of attributes
                orderby_number_start = x.find("[")
                orderby_number_end = x.find("]", orderby_number_start)
                orderby_attribute_start = orderby_number_end + 2
                orderby_attribute_end = x.find("]", orderby_attribute_start)
                orderby_sub_attribute_start = x.find("[", orderby_attribute_end)

                orderby_number = int(x[orderby_number_start + 1 : orderby_number_end])

                if orderby_number in self.orderby:
                    orderby = self.orderby[orderby_number]

                #  get the attribute name and value
                orderby_attribute = x[orderby_attribute_start:orderby_attribute_end]
                orderby_sub_attribute = ""
                if orderby_sub_attribute_start and orderby_sub_attribute_start > 0:
                    orderby_sub_attribute = x[orderby_sub_attribute_start + 1 : -1]
                value = self.get_vars[x]

                orderby["orderby_number"] = orderby_number
                if orderby_sub_attribute:
                    orderby_attribute += f"_{orderby_sub_attribute}"

                if orderby_attribute == "column":
                    orderby[orderby_attribute] = int(value)
                else:
                    orderby[orderby_attribute] = value

                self.orderby[orderby_number] = orderby

        return