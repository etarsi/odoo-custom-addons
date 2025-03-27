from odoo import tools, models, fields, api, _
import base64
import logging
import datetime
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.oauth2 import service_account
_logger = logging.getLogger(__name__)


class PreventaPedido(models.Model):
    _name = "sebigus.preventa.resumen"
    #_inherit = ["mail.thread", "mail.activity.mixin", "image.mixin"]
    _description = "Preventa Pedido"
    name = fields.Char(string="Name")
    fecha = fields.Date(string="Fecha")
    categoria = fields.Many2one('product.category',string="Categoria")
    etapa = fields.Char(string="Etapa")
    compras = fields.Float(string="Compras")
    stock = fields.Float(string="Stock")
    saldos = fields.Float(string="Saldos")
    vendido = fields.Float(string="Vendido")
    compras_ids = fields.One2many('sebigus.preventa.compras','preventa_id','Compras')
    ventas_ids  = fields.One2many('sebigus.preventa.ventas','preventa_id','Ventas')
    spreadsheet_id = fields.Char(string='Google ID')

    def procesar(self):
        self.env["sebigus.preventa.detalle"].search( [("preventa_id", "=", self.id)]).unlink()
        self.env["sebigus.preventa.compras"].search( [("preventa_id", "=", self.id)]).unlink()
        self.env["sebigus.preventa.ventas"].search( [("preventa_id", "=", self.id)]).unlink()
        articulos={}
        stock={}
        compras={}
        ventas={}
        uxb={}
        precio={}
        so={}
        # Busco las ordenes de compra
        for i in self.env['purchase.order'].search([('date_order','>', self.fecha)]):
            vars ={}
            vars['preventa_id'] = self.id 
            #self.env['sebigus.preventa.compras'].create(vars)
            for p in i.order_line:
                if p.product_id.categ_id == self.categoria:
                    articulos[p.product_id.id] = p.product_id.id
                    precio[p.product_id.id] = p.product_id.list_price
                    if p.product_id.id in compras:
                        compras[p.product_id.id] = p.product_id.uom_po_id.factor_inv  + compras[p.product_id.id]
                    else:
                        compras[p.product_id.id] = p.product_id.uom_po_id.factor_inv
                    uxb[p.product_id.id] = p.product_id.uom_po_id.factor_inv
        # Busco las ordenes de venta
        for i in self.env['sale.order'].search([('state','in',['draft','sent','sale']),('date_order','>',self.fecha)]):
            vars={}
            vars['preventa_id'] = self.id 
            for p in i.order_line:
                if p.product_id.categ_id == self.categoria:
                    articulos[p.product_id.id] = p.product_id.id
                    precio[p.product_id.id] = p.product_id.list_price
                    uxb[p.product_id.id] = p.product_id.uom_po_id.factor_inv
                    if p.product_id.id in ventas:
                        ventas[p.product_id.id] = p.product_uom_qty / p.product_id.uom_po_id.factor_inv + ventas[p.product_id.id]
                    else:
                        ventas[p.product_id.id] = p.product_uom_qty / p.product_id.uom_po_id.factor_inv
        # Busco stock actual
        for prod in articulos:
            p = self.env['product.product'].search([('id','=',prod)])
            quants = self.env['stock.quant'].search([('product_id','=',p.id),('location_id','=',22)])
            if quants and quants[0].available_quantity > 0:
                stock[prod] = quants[0].available_quantity 
            else:
                stock[prod] = 0
        # Realizo cuentas de compras / ventas / saldos
        # Cargo detalle de ventas
        # Busco las ordenes de venta
        # Armo lista de SO que solo tienen los archivos de la categoria necesaria
        lista_so = {}
        for sale_o in self.env['sale.order'].search([('state','in',['draft','sent','sale']),('date_order','>',self.fecha)]):
            for p in sale_o.order_line:
                if p.product_id.categ_id == self.categoria:
                    lista_so[sale_o.id]  = sale_o.id
        _logger.info('SO %s' % lista_so)
        clientes = {}
        ordenes = {}
        for i in self.env['sale.order'].search([('state','in',['draft','sent','sale'])]):
            if i.id in lista_so:
                if i.origin:
                    k = i.origin
                else:
                    k = i.name
                if i.partner_id.id not in clientes:
                    clientes[i.partner_id.id] =  {}
                    clientes[i.partner_id.id]['name'] = i.partner_id.name
                    clientes[i.partner_id.id]['descuento'] =  i['order_line'][0].discount
                    clientes[i.partner_id.id]['condiciones'] =  i.partner_id.property_payment_term_id.name
                if i.partner_id.id not in so:
                    so[i.partner_id.id] =  {}
                    so[i.partner_id.id]['unidades'] = 0
                    so[i.partner_id.id]['enviadas'] = 0
                so[i.partner_id.id][i.name] = {}
                so[i.partner_id.id][i.name]['unidades'] = 0
                so[i.partner_id.id][i.name]['enviadas'] = 0
                for p in i.order_line:
                    if p.product_id.id not in so[i.partner_id.id][i.name]:
                        so[i.partner_id.id][i.name][p.product_id.id]= 0
                    if p.product_id.id not in clientes[i.partner_id.id]:
                        clientes[i.partner_id.id][p.product_id.id] =  0
                    so[i.partner_id.id][i.name][p.product_id.id] += p.product_id.uom_po_id.factor_inv
                    so[i.partner_id.id]['unidades'] += p.product_uom_qty
                    so[i.partner_id.id]['enviadas'] += p.qty_delivered
                    so[i.partner_id.id][i.name]['unidades'] += p.product_uom_qty
                    so[i.partner_id.id][i.name]['enviadas'] += p.qty_delivered
                    clientes[i.partner_id.id][p.product_id.id] += p.product_id.uom_po_id.factor_inv

        _logger.info('RESUMEN %s' % clientes)
        # Probamos grabar en google
        SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
        KEY = '/opt/odoo16/16.0/extra-addons/sebigus/static/sebigus-preventa-55f0f156ceb2.json'
        #SPREADSHEET_ID = '1BIqKHnyLGUQ6-dMrrLH52M8AeOIW93m1m_Yt2tL6gtM'
        SPREADSHEET_ID = self.spreadsheet_id

        creds = None
        creds = service_account.Credentials.from_service_account_file(KEY, scopes=SCOPES)

        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        # Preparo articulos
        arts=[]
        for p in articulos:
            prod = self.env['product.product'].search([('id','=',p)])
            v = 0
            com_stock = 0
            stk = 0
            p_venta = 0
            if p in compras:
                com_stock += compras[p]
            if p in stock:
                com_stock +=  stock[p]
            if p in ventas:
                v = ventas[p]
            if com_stock > 0:
                p_venta= (v / com_stock) * 100
            imagen='=image("%s/web/image/product.product/%s/image_256")' % (self.env['ir.config_parameter'].get_param('web.base.url'),p)
            if uxb[p] == 0:
                uxb[p] = 1
            ll = [prod.default_code,p_venta,imagen,prod.name,com_stock/uxb[p],uxb[p],prod.list_price,com_stock / uxb[p] - v,v]
            for c in clientes:
                for o in so[c]:
                    if o not in ['enviadas','unidades']:
                        if p in so[c][o]:
                            ll.append(so[c][o][p])
                        else:
                            ll.append('')
            arts.append(ll)

        result = sheet.values().clear(spreadsheetId=SPREADSHEET_ID,range='A10:ZZ5000').execute()
        # Agrego cantidades por cliente
        titulos = ['CODIGO','% VENTA','IMAGEN','DESCRIPCION','BULTOS TOTALES','UXB','PRECIO','SALDO','VENDIDO']
        tit_so =  [' ',' ',' ',' ',' ',' ',' ',' ',' ']
        avance_so =  [' ',' ',' ',' ',' ',' ',' ',' ','Avance SO']
        avance_tot = [' ',' ',' ',' ',' ',' ',' ',' ','Avance']
        descuentos = [' ',' ',' ',' ',' ',' ',' ',' ','Descuento']
        condiciones= [' ',' ',' ',' ',' ',' ',' ',' ','Condiciones']
        vendedores = [' ',' ',' ',' ',' ',' ',' ',' ','Vendedor ']
        plazos     = [' ',' ',' ',' ',' ',' ',' ',' ','Plazos']
        tipofac    = [' ',' ',' ',' ',' ',' ',' ',' ','Tipo']
        financieros= [' ',' ',' ',' ',' ',' ',' ',' ','Desc.Financieros']
        lista      = [' ',' ',' ',' ',' ',' ',' ',' ','Lista']
        for c in clientes:
            first=True
            for o in so[c]:
                if o not in ['enviadas','unidades']:
                    try:
                        avance_so.append(so[c][o]['enviadas'] / so[c][o]['unidades']) 
                    except:
                        avance_so.append(0)
                    if first:
                        titulos.append('%s' % clientes[c]['name'])
                        #condiciones.append('%s' % clientes[c]['condiciones'])
                        condiciones.append('condiciones')
                        #descuentos.append('%s' % clientes[c]['descuento'])
                        descuentos.append('descuento')
                        try:
                            avance_tot.append(so[c]['enviadas'] / so[c]['unidades']) 
                        except:
                            avance_tot.append(0)
                        first = False
                    else:
                        avance_tot.append('')
                        titulos.append('')
                        descuentos.append('')
                        condiciones.append('')
                        vendedores.append('')
                        plazos.append('')
                        tipofac.append('')
                        financieros.append('')
                        lista.append('')
                    tit_so.append(o)
                
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A10',
							        valueInputOption='USER_ENTERED',
							        body={'values':[avance_tot]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A11',
							        valueInputOption='USER_ENTERED',
							        body={'values':[avance_so]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A1',
							        valueInputOption='USER_ENTERED',
							        body={'values':[condiciones]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A2',
							        valueInputOption='USER_ENTERED',
							        body={'values':[descuentos]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A3',
							        valueInputOption='USER_ENTERED',
							        body={'values':[vendedores]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A4',
							        valueInputOption='USER_ENTERED',
							        body={'values':[tipofac]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A5',
							        valueInputOption='USER_ENTERED',
							        body={'values':[plazos]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A6',
							        valueInputOption='USER_ENTERED',
							        body={'values':[financieros]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A7',
							        valueInputOption='USER_ENTERED',
							        body={'values':[lista]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A12',
							        valueInputOption='USER_ENTERED',
							        body={'values':[titulos]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A13',
							        valueInputOption='USER_ENTERED',
							        body={'values':[tit_so]}).execute()

        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A14',
							        valueInputOption='USER_ENTERED',
							        body={'values':arts}).execute()
        _logger.info("Datos insertados correctamente")
        url = "https://docs.google.com/spreadsheets/d/%s" % self.spreadsheet_id
        return {
                'type': 'ir.actions.act_url',
                'url': url,
                'target': 'new',
        }

class PreventaPedidoCompras(models.Model):
    _name = "sebigus.preventa.compras"
    _description = "Preventa Compras"
    preventa_id = fields.Many2one('sebigus.preventa.resumen',string='Preventa')

class PreventaPedidoVentas(models.Model):
    _name = "sebigus.preventa.ventas"
    _description = "Preventa Ventas"
    preventa_id = fields.Many2one('sebigus.preventa.resumen',string='Preventa')



class PreventaPedidoDetalle(models.Model):
    _name = "sebigus.preventa.detalle"
#   _inherit = ["mail.thread", "mail.activity.mixin", "image.mixin"]
    _description = "Preventa Detalle"

    producto = fields.Many2one('product.product','Products', required=True)
    saleorder = fields.Many2one('sale.order','Orden de venta', required=True)
    cliente = fields.Char(string='Cliente')
    bultos = fields.Float(string="Bultos")
    uxb = fields.Integer( string="UxB")
    image = fields.Image( string="Image")
    name = fields.Char(string="Name")
    preventa_id = fields.Many2one("sebigus.preventa.resumen", string="Preventa")
    description = fields.Char(string="Descripcion")
   #product_id = fields.One2many(string="Codigo")
   #user_id = fields.Many2one("res.users", string="Cliente")
   #partner_id = fields.Many2one("res.partner", string="Empresa", required=True)
   #cliente = fields.Char(string='Cliente')
   #list_price = fields.Monetary(string="Precio")
   #currency_id = fields.Many2one(
   #    "res.currency", "Currency", compute="_compute_currency_id"
   #)
   #uxb = fields.Integer( string="UxB")
   #quantity = fields.Integer(string="Unidades")
   #catalogo = fields.Char(string="Catalogo")
   #etapa = fields.Char(string="Etapa")
   #licencia = fields.Char(string="Licencia")
   #order_id = fields.Char(string="Numero")
   #sale_order_id = fields.Integer(string="Orden de venta")
   #unidades_demanda = fields.Float(string="Unidades Demanda")
   #bultos_pedidos = fields.Float(string="Bultos Pedidos")
