# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.tools.image import image_data_uri


import logging
_logger = logging.getLogger(__name__)

class Sebigus(http.Controller):
    @http.route('/sebigus/sebigus', auth='user', website=True)
    def index(self, **kw):
        pedidos_data = request.env['sale.order'].sudo().search(['&',('state','=','draft'),('user_id','=',request.uid)])
        values = {
                   'records': pedidos_data
                 } 
        return request.render('sebigus.pedido', values)
        
    @http.route('/sebigus/sebigus/procesar_carga', auth='user', website=True)
    def procesar_carga(self, **kw):
        pedido_id= kw.get('pedido_id')
        codigo= kw.get('codigo')
        cajas= kw.get('cajas')
        unidades= kw.get('unidades')
        sale_order_obj = request.env['sale.order']
        product_obj = request.env['product.product']
        sale_order_line_obj = request.env['sale.order.line']
        product_id = product_obj.search([('default_code','=',codigo)])
        _logger.info('Producto: %s' % product_id)
        sale_order_id = sale_order_obj.search([('id','=',pedido_id)])
        cantidad = float(cajas) *  product_obj.uom_po_id.ratio
        quants = request.env['stock.quant'].sudo().search([('product_id','=',product_id.id),('location_id','=',8)])
        if quants and quants[0].available_quantity > 0:
            _logger.info('Hay stock disponible')
        else:
            for p in product_id.alternative_product_ids:
                quants = request.env['stock.quant'].sudo().search([('product_id','=',p.id),('location_id','=',8)])
                if quants and quants[0].available_quantity > 0:
                    _logger.info('No hay stock, reridijo a pantalla para reemplazo')
                    return request.redirect('sebigus/sebigus/reemplazo/?pedido_id=%s&codigo=%s' % (pedido_id,product_id.default_code))
            _logger.info('No hay stock, pero no hay productos para reemplazar')
        try:
            if float(cajas)  > 0:
                cantidad = float(cajas) *  product_id.uom_po_id.ratio
            else:
                cantidad = unidades
        except:
            cantidad = 1
        quantity = float(cantidad)
        _logger.info('Cantidad: %s ' % cantidad)
        taxes = product_id.taxes_id.filtered(lambda r: not product_id.company_id or r.company_id == product_id.company_id)
        tax_ids = taxes.ids
        if codigo and cantidad:
           ## cargo nuevo producto al pedido
            _logger.info('Cargo un nuevo producto')
            if sale_order_id and product_id:
                sale_order_line_obj.search([('order_id','=',sale_order_id.id),('product_id', '=' , product_id.id)]).unlink()
                _logger.info('Producto: %s' % product_id)
                vals = {
                    'order_id': sale_order_id.id,
                    'product_id': product_id.id,
                    'product_uom_qty': float(quantity),
                    'product_uom': product_id.uom_id.id,
                    'name': product_id.name,
                    'tax_id' : [(6,0,tax_ids)],
                }
                _logger.info('Producto: %s' % vals)
                new = sale_order_line_obj.sudo().create(vals)
                new._compute_name()

        return request.redirect('sebigus/sebigus/cargar/?pedido_id=%s' % pedido_id)

    @http.route('/sebigus/sebigus/pedido', auth='user', website=True)
    def detalle(self, **kw):
        pedido_id= kw.get('pedido_id')
        pedido = request.env['sale.order'].sudo().search([('id','=',pedido_id)])
        cliente = pedido.partner_id.name if pedido.partner_id.is_company else pedido.partner_id.commercial_partner_id.name
        values = {
                   'records': pedido,
                   'cliente': cliente
                 } 
        return request.render('sebigus.pedido_detalle', values)
    @http.route('/sebigus/sebigus/cargar', auth='user', website=True)
    def cargar(self, **kw):
        pedido_id= kw.get('pedido_id')
        pedido = request.env['stock.picking'].sudo().search([('id','=',pedido_id)])
        values = {
                   'records': pedido
                 } 
        return request.render('sebigus.producto_scan', values)
    @http.route('/sebigus/sebigus/confirmar', auth='user', website=True)
    def confirmar(self, **kw):
        pedido_id= kw.get('pedido_id')
        pedido = request.env['sale.order'].sudo().search([('id','=',pedido_id)])
        pedido.action_confirm()
        return request.redirect('sebigus/sebigus')

    @http.route('/sebigus/sebigus/reemplazo', auth='user', website=True)
    def reemplazo(self, **kw):
        codigo= kw.get('codigo')
        # Busco 
        prod = request.env['product.template'].sudo().search([('default_code','=',codigo)])
        producto = request.env['product.template'].sudo().browse(prod.alternative_product_ids)
        _logger.info(prod.alternative_product_ids)
        _logger.info(producto)
        prod_q = []
        for p in prod.alternative_product_ids:
            quants = request.env['stock.quant'].sudo().search([('product_id','=',p.id),('location_id','=',8)])
            if quants and quants[0].available_quantity > 0:
                prod_q.append(p)
                _logger.info(p,quants[0])

        values = {
                   'records': prod_q,
                   'pedido_id' : kw.get('pedido_id'),
                   'cantidad' : 0,
                   'bultos' : 0,
                 } 
        return request.render('sebigus.producto_reemplazo', values)
    @http.route('/sebigus/sebigus/cantidad', auth='user', website=True)
    def cantidad(self, **kw):
        ean= kw.get('ean')
        codigo= kw.get('codigo')
        pedido_id= kw.get('pedido_id')
        _logger.info('EAN: %s' % ean)
        _logger.info('CODIGO: %s' % codigo)
        cantidad_pedida =  0;
        cantidad_pedida_bultos = 0;
        if codigo:
            producto = request.env['product.template'].sudo().search([('default_code','=',codigo)])
            if not producto:
                producto = request.env['product.template'].sudo().search([('barcode','=',codigo)])
        else:
            producto = request.env['product.template'].sudo().search([('barcode','=',ean)])
        _logger.info('Producto: %s' % producto)
        product_obj = request.env['product.product']
        product_id = product_obj.search([('default_code','=',producto.default_code)])
        quants = request.env['stock.quant'].sudo().search([('product_id','=',product_id.id),('location_id','=',8)])
        if quants:
            cantidad = quants[0].available_quantity
            bultos = quants[0].available_quantity / producto[0].uom_po_id.ratio
        else:
            cantidad = 0
            bultos = 0
        # Busco si ya esta en la orden de venta
        sale_order_obj = request.env['sale.order']
        sale_order_id = sale_order_obj.search([('id','=',pedido_id)])
        product_obj = request.env['product.product']
        product_id = product_obj.search([('default_code','=',codigo)])
        for line in sale_order_id.order_line:
            _logger.info('%s' % line.product_id)
            if line.product_id.id == product_id.id:
                cantidad_pedida = line.product_uom_qty
                cantidad_pedida_bultos = line.product_packaging_qty
        values = {
                   'records': producto,
                   'cantidad' : cantidad,
                   'bultos' : bultos,
                   'cantidad_pedida': cantidad_pedida,
                   'cantidad_pedida_bultos': cantidad_pedida_bultos,
                 } 
        _logger.info('%s' % values)
        return request.render('sebigus.producto_cantidad', values)

    @http.route('/sebigus/sebigus/productos', auth='user', website=True)
    def productos(self, **kw):
        from odoo.addons.sebigus.models.datatable import DataTablesResponse, DataTablesField, DataTablesButton
       #btn_edit=A('Editar',_class='btn btn-primary',_href=URL('usuario',vars={'user_id':'record_id'}),_onclick="modal_wait();")
       #btn_detalle=A('Detalle',_class='btn btn-primary',_href=URL('detalle_usuario',vars={'user_id':'record_id'}),_onclick="modal_wait();")
       #btn_edit=DataTablesButton('edita','Editar','fa fa-edit',href=URL('usuario',vars={'user_id':'record_id'}),onclick="modal_wait();")
       #btn_detalle=DataTablesButton('detalle','Detalle','fa fa-detail',href=URL('detalle_usuario',vars={'user_id':'record_id'}),onclick="modal_wait();")
       #btn_moroso=DataTablesButton('moroso','Moroso','fa fa-money',href=URL('cambiar_moroso',vars={'user_id':'record_id'}),onclick="modal_wait();")
        dt = DataTablesResponse(
            fields=[
                DataTablesField(name="DT_RowId", visible=False),
                DataTablesField(name="id"),
                DataTablesField(name="firstname"),
                DataTablesField(name="lastname"),
                DataTablesField(name="username"),
                DataTablesField(name="moroso",orderable="false"),
            ],
           #data_url=URL("usuarios_data"),
           #buttons=[btn_edit,btn_detalle,btn_moroso],
            sort_sequence=[[1, "asc"]],
        )
        values = {
                   'table': dt.table(),
                   'scripts': dt.script(),
                 } 
        return request.render('sebigus.productos', values)