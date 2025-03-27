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
        # Busco las ordenes de compra
        for i in self.env['purchase.order'].search([('id','>', 0)]):
            vars ={}
            vars['preventa_id'] = self.id 
            #self.env['sebigus.preventa.compras'].create(vars)
            for p in i.order_line:
                articulos[p.product_id.id] = p.product_id.id
                precio[p.product_id.id] = p.product_id.list_price
                if p.product_id.id in compras:
                    compras[p.product_id.id] = p.product_packaging_qty  + compras[p.product_id.id]
                else:
                    compras[p.product_id.id] = p.product_packaging_qty  
                uxb[p.product_id.id] = p.product_packaging_id.qty
        # Busco las ordenes de venta
        for i in self.env['sale.order'].search([('id','>', 0)]):
            vars ={}
            vars['preventa_id'] = self.id 
            #self.env['sebigus.preventa.ventas'].create(vars)
            for p in i.order_line:
                articulos[p.product_id.id] = p.product_id.id
                precio[p.product_id.id] = p.product_id.list_price
                uxb[p.product_id.id] = p.product_packaging_id.qty
                if p.product_id.id in ventas:
                    ventas[p.product_id.id] = p.product_packaging_qty  + ventas[p.product_id.id]
                else:
                    ventas[p.product_id.id] = p.product_packaging_qty  
        # Busco stock actual
        for prod in articulos:
            p = self.env['product.product'].search([('id','=',prod)])
            quants = self.env['stock.quant'].search([('product_id','=',p.id),('location_id','=',8)])
            if quants and quants[0].available_quantity > 0:
                stock[prod] = quants[0].available_quantity 
            else:
                stock[prod] = 0
        # Con los productos ya listados, preparo el detalle por cliente
        _logger.info(articulos)
        for p in articulos:
            det = {}
            det['preventa_id'] = self.id 
            det['cliente'] = '0 - % VENTA'
            det['producto'] = p
            det['description'] = p
            det['uxb'] = uxb[p]
            det['bultos'] = 0
            com_stock = 0
            v = 0
            if p in compras:
                com_stock += compras[p]
            if p in stock:
                com_stock +=  stock[p]
            if p in ventas:
                v = ventas[p]
            if com_stock > 0:
                det['bultos'] = (v / com_stock) * 100
            #self.env['sebigus.preventa.detalle'].create(det)

            det = {}
            det['preventa_id'] = self.id 
            det['cliente'] = '0 - BULTOS TOTALES'
            det['producto'] = p
            det['description'] = p
            det['uxb'] = uxb[p]
            det['bultos'] = 0
            if p in compras:
                det['bultos'] += compras[p]
            if p in stock:
                det['bultos'] +=  stock[p]
            #self.env['sebigus.preventa.detalle'].create(det)

            det = {}
            det['preventa_id'] = self.id 
            det['cliente'] = '1 - UXB'
            det['producto'] = p
            det['description'] = p
            det['bultos'] = uxb[p]
            det['uxb'] = uxb[p]
            #self.env['sebigus.preventa.detalle'].create(det)
            
            det = {}
            det['preventa_id'] = self.id 
            det['cliente'] = '2 - PRECIO'
            det['producto'] = p
            det['description'] = p
            det['bultos'] = precio[p]
            det['uxb'] = uxb[p]
            #self.env['sebigus.preventa.detalle'].create(det)
            
            det = {}
            det['preventa_id'] = self.id 
            det['cliente'] = '3 - SALDO'
            det['producto'] = p
            det['description'] = p
            det['uxb'] = uxb[p]
            det['bultos'] = 0
            if p in compras:
                det['bultos'] += compras[p]
            if p in stock:
                det['bultos'] +=  stock[p]
            if p in ventas:
                det['bultos'] -= ventas[p]
            #self.env['sebigus.preventa.detalle'].create(det)

            det = {}
            det['preventa_id'] = self.id 
            det['cliente'] = '4 - VENDIDO'
            det['producto'] = p
            det['description'] = p
            if p in ventas:
                det['bultos'] = ventas[p]
            else:
                det['bultos'] = 0
            det['uxb'] = uxb[p]
            #self.env['sebigus.preventa.detalle'].create(det)


        # Realizo cuentas de compras / ventas / saldos
        # Cargo detalle de ventas
        # Busco las ordenes de venta
        clientes = {}
        so = {}
        for i in self.env['sale.order'].search([('id','>', 0)]):
            if i.partner_id.id not in clientes:
                clientes[i.partner_id.id] =  {}
                clientes[i.partner_id.id]['name'] = i.partner_id.name
            if i.partner_id.id not in so:
                so[i.partner_id.id] =  {}
                so[i.partner_id.id]['unidades'] = 0
                so[i.partner_id.id]['enviadas'] = 0
            so[i.partner_id.id][i.name] = {}
            so[i.partner_id.id][i.name]['unidades'] = 0
            so[i.partner_id.id][i.name]['enviadas'] = 0
            det ={}
            det['preventa_id'] = self.id 
            det['saleorder'] = i.id 
            det['cliente'] = i.partner_id.name
            for p in i.order_line:
                if p.product_id.id not in so[i.partner_id.id][i.name]:
                    so[i.partner_id.id][i.name][p.product_id.id]= 0
                if p.product_id.id not in clientes[i.partner_id.id]:
                    clientes[i.partner_id.id][p.product_id.id] =  0
                so[i.partner_id.id][i.name][p.product_id.id] += p.product_packaging_qty
                so[i.partner_id.id]['unidades'] += p.product_uom_qty
                so[i.partner_id.id]['enviadas'] += p.qty_delivered
                so[i.partner_id.id][i.name]['unidades'] += p.product_uom_qty
                so[i.partner_id.id][i.name]['enviadas'] += p.qty_delivered
                clientes[i.partner_id.id][p.product_id.id] += p.product_packaging_qty
                det['description'] = p.product_id.id
                det['producto'] = p.product_id.id
                det['uxb'] = uxb[p.product_id.id]
                det['image'] = p.product_id.image_128
                det['bultos'] = p.product_packaging_qty  
                #self.env['sebigus.preventa.detalle'].create(det)

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
            if p in compras:
                com_stock += compras[p]
            if p in stock:
                com_stock +=  stock[p]
            if p in ventas:
                v = ventas[p]
            if com_stock > 0:
                p_venta= (v / com_stock) * 100
            imagen='=image("https://ventas.sebigus.com.ar/web/image/product.product/%s/image_128")' % p
            ll = [prod.default_code,p_venta,imagen,prod.name,com_stock,uxb[p],prod.list_price,com_stock - v,v]
            for c in clientes:
                for o in so[c]:
                    if o not in ['enviadas','unidades']:
                        if p in so[c][o]:
                            ll.append(so[c][o][p])
                        else:
                            ll.append('')
            arts.append(ll)

        result = sheet.values().clear(spreadsheetId=SPREADSHEET_ID,range='A5:ZZ5000').execute()
        # Agrego cantidades por cliente
        titulos = ['CODIGO','% VENTA','IMAGEN','DESCRIPCION','BULTOS TOTALES','UXB','PRECIO','SALDO','VENDIDO']
        tit_so =  [' ',' ',' ',' ',' ',' ',' ',' ',' ']
        avance_so =  [' ',' ',' ',' ',' ',' ',' ',' ','Avance SO']
        avance_tot = [' ',' ',' ',' ',' ',' ',' ',' ','Avance']
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
                        try:
                            avance_tot.append(so[c]['enviadas'] / so[c]['unidades']) 
                        except:
                            avance_tot.append(0)
                        first = False
                    else:
                        avance_tot.append('')
                        titulos.append('')
                    tit_so.append(o)
        _logger.info('%s' % titulos)
                
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A5',
							        valueInputOption='USER_ENTERED',
							        body={'values':[avance_tot]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A6',
							        valueInputOption='USER_ENTERED',
							        body={'values':[avance_so]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A7',
							        valueInputOption='USER_ENTERED',
							        body={'values':[titulos]}).execute()
        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A8',
							        valueInputOption='USER_ENTERED',
							        body={'values':[tit_so]}).execute()

        result = sheet.values().update(spreadsheetId=SPREADSHEET_ID,
							        range='A9',
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
