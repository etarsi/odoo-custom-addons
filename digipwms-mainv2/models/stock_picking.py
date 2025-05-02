from odoo import tools, models, fields, api, _
import html2text
from odoo.exceptions import UserError, ValidationError
import logging
import requests
from requests.structures import CaseInsensitiveDict
import re
import math
from collections import defaultdict
null=None

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    state_wms = fields.Selection([('closed','Enviado y recibido'),('done','Enviado'),('no','No enviado'),('error','Error envio'),('pending', 'Pendiente')],string='Estado WMS',default='no',copy=False,tracking=True)
    codigo_wms = fields.Char(string='Codigo WMS',copy=False,tracking=True)
    container = fields.Char(string='Container',copy=False)


    def send_incoming(self):
        return True

    def get_bultos(self, cod_pedido):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get(f'{url}/v1/Pedidos/%s/Contenedores' % cod_pedido, headers=headers)
        if respGet.status_code not in [200, 201] or respGet.content.strip() == b'null':
            return False
        json_response = respGet.json()
        cantidad = 0
        for j in json_response:
            if 'CantidadBulto' in j:
                cantidad += j['CantidadBulto']
        return cantidad


    def get_stock(self, codigo):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get(f'{url}/v1/Stock/PorArticulo/{codigo}', headers=headers)
        if respGet.status_code not in [200, 201] or respGet.content.strip() == b'null':
            _logger.info('STOCK %s ' % respGet.status_code )
            return 0

        json_response = respGet.json()
        _logger.info('STOCK %s' % json_response)
        unidades = 0
        for j in json_response:
            if 'UnidadesDisponibles' in j:
                unidades =  j['UnidadesDisponibles'] 
        return unidades

    def get_stocks(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get(f'{url}/v1/Stock', headers=headers)
        if respGet.status_code not in [200, 201] or respGet.content.strip() == b'null':
            _logger.info('STOCK %s ' % respGet.status_code )
            return [0]

        json_response = respGet.json()
        unidades = 0
        codigos = {}
        for j in json_response:
            if 'UnidadesDisponibles' in j:
                codigos[j['CodigoArticulo']] =  j['UnidadesDisponibles'] 
        return codigos

    def get_stocksv2(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.urlv2')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get(f'{url}/v2/Stock/Tipo', headers=headers)
        if respGet.status_code not in [200, 201] or respGet.content.strip() == b'null':
            _logger.info('STOCK %s ' % respGet.status_code )
            return None

        json_response = respGet.json()
        unidades = 0
        codigos = {}
        for j in json_response:
            if 'stock' in j and 'disponible' in j['stock']:
                codigos[j['codigo']] =  j['stock']['disponible']
        return codigos

    def create_update_cliente(self,p):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        if p.partner_id.parent_id:
            respGet = requests.get('%s/v1/Clientes/%s' % (url,'o'+str(p.partner_id.parent_id.id)), headers=headers)
        else:
            respGet = requests.get('%s/v1/Clientes/%s' % (url,'o'+str(p.partner_id.id)), headers=headers)
        _logger.info(('---GET----cliente--->',respGet))
        if respGet.status_code not in [200,201] or respGet.content.strip() == b'null':
            new = {}
            if p.partner_id.parent_id:
                new["Codigo"]= 'o' + str(p.partner_id.parent_id.id)
                new["Descripcion"]= p.partner_id.parent_id.name
                new["IdentificadorFiscal"]= p.partner_id.parent_id.vat
                new["Activo"]= p.partner_id.parent_id.active
            else:
                new["Codigo"]= 'o' + str(p.partner_id.id)
                new["Descripcion"]= p.partner_id.name
                new["IdentificadorFiscal"]= p.partner_id.vat
                new["Activo"]= p.partner_id.active
            respPost = requests.post('%s/v1/Clientes' % url, headers=headers, json=new)
            _logger.info(('----POST---cliente--->',respPost))
        return True

    def create_update_proveedor(self,p):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get('%s/v1/Proveedor/%s' % (url,'o'+str(p.partner_id.id)), headers=headers)
        _logger.info(('---GET---Prov---->',respGet,respGet.content.strip()))
        if respGet.status_code not in [200,201] or respGet.content.strip() == b'null':
            data = {
                  "Codigo": 'o' + str(p.partner_id.id),
                  "Descripcion": p.partner_id.name,
                  "RequiereControlCiego": p.partner_id.active,
                  "Activo": p.partner_id.active
            }
            respPost = requests.post('%s/v1/Proveedor' % url, headers=headers, json=data)
            _logger.info(('----POST---Prov--->',respPost))
        return True
    def cargo_stock_desde_digipv2(self,records):
        stock_codigo = self.get_stocksv2()
        if not stock_codigo:
            raise UserError('No se pudo obtener stock de digip')
        con_stock = {}
        for sp in records:
            self.env['stock.move.line'].search([('picking_id','=', sp.id)]).unlink()
            for move in sp.move_ids_without_package:
                codigo = '%s' % move.product_id.default_code
                if codigo[0] == '9':
                    codigo = codigo[1:]
                if codigo in stock_codigo and stock_codigo[codigo]  > 0:
                    move.write({'quantity_done': 0})
                    try:
                        if move.product_uom_qty <= stock_codigo[codigo]:
                            move.write({'quantity_done': move.product_uom_qty })
                            stock_codigo[codigo] = stock_codigo[codigo] - move.product_uom_qty 
                        else:
                            move.write({'quantity_done': stock_codigo[codigo] })
                            stock_codigo[codigo] = 0
                    except Exception as Ex:
                        raise ValidationError('Codigos no se puede cambiar la cantidad %s %s . ' % (move.product_id.default_code, Ex))

    def cargo_stock_desde_digip(self):
        stock_codigo = self.get_stocks()
        con_stock = {}
#   '''
#       for sps in sp.env['stock.picking'].sudo().search([('state_wms','in',['done']),('state','not in',['draft','done','cancel'])]):
#           for c in sps.move_ids_without_package:
#               if c.product_id.default_code in con_stock:
#                   con_stock[c.product_id.default_code] = con_stock[c.product_id.default_code] - c.quantity_done
#               else:
#                   con_stock[c.product_id.default_code] = c.quantity_done
#       # Busco todos las ordes del mismo pedido para controlar el stock todo junto
#       stock_pickings = []
#       stock_pickings.append(self)
#       for company in self._context.get('allowed_company_ids'):
#           # Busco el hay otros envios para la misma orden de venta
#           if company != self.company_id.id:
#               sale_name = saleorder.name.split(' ')[0]
#               sps = sp.env['stock.picking'].sudo().search([('company_id','=',company),('state_wms','in',['no','error']),('origin', 'ilike', str(sale_name)),('state','not in',['draft','done','cancel'])],limit=1,order='id desc')
#               stock_pickings.append(sps)
#       for picking in stock_pickings:
#           if picking.codigo_wms:
#               cod_pedido = picking.codigo_wms
#           else:
#               cod_pedido = self.env['ir.sequence'].sudo().next_by_code('DIGIP')
#       for picking in stock_pickings:
#           picking.sudo().write({'codigo_wms':cod_pedido})
#           for move in picking.move_ids_without_package:
#               # Access product_id and product_uom_qty
#               product_code = move.product_id.default_code
#               quantity = move.product_uom_qty
#               # Accumulate quantities by product_code in the dictionary
#               product_dict[product_code] += quantity
#       for picking in stock_pickings:
#           for move in self.move_ids_without_package:
#               if move.product_id.default_code in stock_codigo and stock_codigo[move.product_id.default_code]  > 0:
#                   try:
#                       product_code = move.product_id.default_code
#                       if product_dict[product_code] <= stock_codigo[move.product_id.default_code]:
#                       #if move.product_uom_qty <= stock_codigo[move.product_id.default_code]:
#                           move.write({'quantity_done': move.product_uom_qty })
#                       else:
#                           ratio = det.product_uom_qty/r['Unidades']
#                           move.write({'quantity_done': round(ratio * stock_codigo[move.product_id.default_code],0) })
#                   except:
#                       raise ValidationError('Codigos no se puede cambiar la cantidad %s . ' % move.product_id.default_code)

#       if len(stock_pickings) > 1:
#             return {
#                     'type': 'ir.actions.client',
#                     'tag': 'display_notification',
#                     'params': { 'title': _("El pidido que esta controlando tiene 2 partes",),
#                                 'type': 'success',
#                                 'sticky': False,
#                                 'next': {'type': 'ir.actions.act_window_close'}, 
#                               },
#                    }


#       '''

        self.env['stock.move.line'].search([('picking_id','=', self.id)]).unlink()
        for move in self.move_ids_without_package:
            codigo = '%s' % move.product_id.default_code
            if codigo[0] == '9':
                codigo = codigo[1:]
            if codigo in stock_codigo and stock_codigo[codigo]  > 0:
                move.write({'quantity_done': 0})
                try:
                    if move.product_uom_qty <= stock_codigo[codigo]:
                        move.write({'quantity_done': move.product_uom_qty })
                        stock_codigo[codigo] = stock_codigo[codigo] - move.product_uom_qty 
                    else:
                        move.write({'quantity_done': stock_codigo[codigo] })
                        stock_codigo[codigo] = 0
                except Exception as Ex:
                    raise ValidationError('Codigos no se puede cambiar la cantidad %s %s . ' % (move.product_id.default_code, Ex))


    def create_update_ubicacion_xx(self,p):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get('%s/v1/Cliente/%s/ClientesUbicaciones' % (url,'u'+str(p.partner_id.id)), headers=headers)
        _logger.info(('---GET--create ubicacion----->',respGet))
        if respGet.status_code != 200 and respGet.status_code != 201:
          new = {}
          new["Codigo"]= 'u' + str(p.partner_id.id)
          new["Descripcion"]= p.partner_id.name
          if p.partner_id.parent_id:
              new["Descripcion"]= '%s - %s' % (p.partner_id.name , p.partner_id.parent_id.name )
          new["Direccion"]= str(p.partner_id.street)
          if p.partner_id.street2:
             new["Direccion"] += ' ' + str(p.partner_id.street2)
          new["Localidad"]= p.partner_id.city
          new["Email"]= p.partner_id.email
          if p.partner_id.state_id:
             new["Provincia"]= p.partner_id.state_id.name
          new["Activo"]= p.partner_id.active
          if p.partner_id.parent_id:
              respPost = requests.post('%s/v1/Cliente/%s/ClientesUbicaciones' % (url,'o'+str(p.partner_id.parent_id.id)), headers=headers, json=new)
          else:
              respPost = requests.post('%s/v1/Cliente/%s/ClientesUbicaciones' % (url,'o'+str(p.partner_id.id)), headers=headers, json=new)
          _logger.info('----POST----ubicacion--> %s %s %s ' % (respPost,respPost.content,new))
        return True


    def create_update_ubicacion(self,p):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get('%s/v1/Cliente/ClientesUbicaciones/%s' % (url,'u'+str(p.partner_id.id)), headers=headers)
        _logger.info(('---GET--create ubicacion----->',respGet))
        new = {}
        new["Codigo"]= 'u' + str(p.partner_id.id)
        new["Descripcion"]= p.partner_id.name
        if p.partner_id.parent_id:
            new["Descripcion"]= '%s - %s' % (p.partner_id.name , p.partner_id.parent_id.name )
        new["Direccion"]= str(p.partner_id.street)
        if p.partner_id.street2:
           new["Direccion"] += ' ' + str(p.partner_id.street2)
        new["Localidad"]= p.partner_id.city
        new["Email"]= p.partner_id.email
        if p.partner_id.state_id:
           new["Provincia"]= p.partner_id.state_id.name
        # Cambiamos la provincia por el transportista y en el la localidad ponemos la provincia
        new["Localidad"]= '%s / %s' % (new["Localidad"],new["Provincia"])
        new["Provincia"]=str(p.carrier_id.name) if p.carrier_id else " "

        new["Activo"]= p.partner_id.active
        if respGet.status_code != 200 and respGet.status_code != 201:
          if p.partner_id.parent_id:
              respPost = requests.post('%s/v1/Cliente/%s/ClientesUbicaciones' % (url,'o'+str(p.partner_id.parent_id.id)), headers=headers, json=new)
          else:
              respPost = requests.post('%s/v1/Cliente/%s/ClientesUbicaciones' % (url,'o'+str(p.partner_id.id)), headers=headers, json=new)
        else:
          if p.partner_id.parent_id:
              respPost = requests.put('%s/v1/Cliente/%s/ClientesUbicaciones/%s' % (url,'o'+str(p.partner_id.parent_id.id),new['Codigo']), headers=headers, json=new)
          else:
              respPost = requests.put('%s/v1/Cliente/%s/ClientesUbicaciones/%s' % (url,'o'+str(p.partner_id.id),new['Codigo']), headers=headers, json=new)

          _logger.info('----POST----ubicacion--> %s %s %s ' % (respPost,respPost.content,new))
        return True


    def create_update_articulo(self,p):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get('%s/v1/Articulos/%s' % (url,str(p.default_code)), headers=headers)
        _logger.info(('---GET-------ARTICULO ALTA >',respGet))
        if respGet.status_code != 200 and respGet.status_code != 201:
           new = {}
           new["CodigoArticulo"]= p.default_code
           new["Descripcion"]= '%s - %s' % (p.default_code, p.name)
           new["DiasVidaUtil"]= 9999
           new["UsaLote"]= False
           new["UsaSerie"]= False
           new["UsaVencimiento"]= False
           new["EsVirtual"]= False
           new["ArticuloTipoRotacion"]= "alta"
           new["Activo"]= True
           new["UsaPesoDeclarado"]= False
           new["PesoDeclaradoPromedio"]= 0
           respPost = requests.post('%s/v1/Articulos' % url, headers=headers, json=new)
           _logger.info(('---ALTA ',respGet.content))
        return True



    def enviar(self):
        if self.state_wms != 'no':
            raise UserError('El pedido ya fué enviado a Digip')
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        # Busco los envios pendiente que tiene el documento de origen de la SO
        # Genero un solo documento do SO
        # Envio cabecera
        # Genero un nuveo numero de id para los envios
        sp = self
        #cod_pedido = re.sub('/','_',sp.name)
        if ('Preparacion' not in sp.picking_type_id.name) and ('Fabricaci' not in sp.picking_type_id.name):
            if not sp.picking_type_code =='outgoing' or not sp.origin:
                _logger.info('WMS Sale porque no es valido %s' % sp.picking_type_id.name)
                return False
        product_dict = defaultdict(float)
        saleorder = sp.env['sale.order'].sudo().search([('name','=',str(sp.origin)[:6]),('state','in',['sale','done','cancel'])],limit=1)
        saleorder = sp.env['sale.order'].sudo().search([('name','=',str(sp.origin)),('state','in',['sale','done','cancel'])],limit=1)
        if not saleorder:
            return False
        # Corrijo metodo de entrega
        if self.partner_id.property_delivery_carrier_id:
            self.write({'carrier_id':self.partner_id.property_delivery_carrier_id})

        #cod_pedido = re.sub('/','_',saleorder.name)
        # Preparo una lista de stock picking,  pero solo me quedo con 1 de cada compañia, y el mas antiguo
        # Esto es para enviar solo 1 cuando se hace un split manual y el nuevo  se deja como backorder
        stock_pickings = []
        stock_pickings.append(self)
        for company in self._context.get('allowed_company_ids'):
            # Busco el hay otros envios para la misma orden de venta
            if company != self.company_id.id:
                sale_name = saleorder.name.split(' ')[0]
                sps = sp.env['stock.picking'].sudo().search([('company_id','=',company),('state_wms','in',['no','error']),('origin', 'ilike', str(sale_name)),('state','not in',['draft','done','cancel'])],limit=1,order='id desc')
                stock_pickings.append(sps)
        if not stock_pickings:
            return False
        # Verifico que todos los productos tengan stock antes de enviar
        sinstock=True
        stock_codigos = self.get_stocks()
        packaging_qty= 0
        for picking in stock_pickings:
             packaging_qty = packaging_qty + picking.packaging_qty
             for move in picking.move_ids_without_package:
                  # Access product_id and product_uom_qty
                  product_code = move.product_id.default_code
                  if product_code[0] == '9':
                      product_code = product_code[1:]
                  quantity = move.product_uom_qty
                  if product_code in stock_codigos and stock_codigos[product_code]  > 0:
                      sinstock=False
        if sinstock:
            raise ValidationError('El pedido no se puede enviar, no hay stock para niguna de las lineas.')
       #if self.codigo_wms:
       #    cod_pedido = self.codigo_wms
       #else:
       #    cod_pedido = self.env['ir.sequence'].sudo().next_by_code('DIGIP')
       #    
       #for picking in stock_pickings:
       #    picking.sudo().write({'codigo_wms':cod_pedido})
       #self.env.cr.commit()

        cod_pedido = self.env['ir.sequence'].sudo().next_by_code('DIGIP')
        _logger.info(cod_pedido)
        _logger.info(stock_pickings)
        respGet = requests.get('%s/v1/Pedidos/%s' % (url,cod_pedido), headers=headers)
        _logger.info(respGet)
        if respGet.status_code not in [200,201] or respGet.content.strip() == b'null':
           self.create_update_cliente(sp)
           self.create_update_ubicacion(sp)
           newc={}
           newc["Codigo"]= cod_pedido
           newc["CodigoClienteUbicacion"]= 'u'+str(sp.partner_id.id)
           newc["PedidoEstado"]= "pendiente"
           newc["Fecha"]= sp.create_date.strftime('%Y-%m-%d %H:%M:%S')
           newc["FechaEstimadaEntrega"]= sp.scheduled_date.strftime('%Y-%m-%d %H:%M:%S')
           newc["Observacion"]= html2text.html2text(str(saleorder.internal_notes)) if saleorder.internal_notes else " "
           newc["Importe"]= str(saleorder.amount_total)
           newc["CodigoDespacho"]= str(sp.carrier_id.name) if sp.carrier_id else " "
           if sp.carrier_id.partner_id:
               newc["CodigoDespacho"] = '%s %s' % (newc["CodigoDespacho"], sp.carrier_id.partner_id.name)
           newc["CodigoDeEnvio"]= saleorder.name
           newc["ServicioDeEnvioTipo"]= "propio"
           newc["PedidoTag"]= ["{:.2f}".format(packaging_qty)]
           _logger.info('----- ALTA PEDIDO ---- %s' % newc)
           respPost = requests.post('%s/v1/Pedidos' % (url), headers=headers, json=newc)
           _logger.info('----- ALTA PEDIDO ----- %s %s %s ' % (respPost.status_code,respPost.content,newc) )
           if respPost.status_code not in [200,201]:
                raise ValidationError('Error al crear pedido %s %s %s.' % (respPost.status_code,respPost.content,newc))
           # Envio detalle
           # Busco los codigos pendientes, y los pongo todos juntos, para enviarlos de una sola vez
           #for det in sp.move_ids_without_package:
           for det in saleorder.order_line:
               if det.product_id.default_code not in stock_codigos:
                   self.create_update_articulo(det.product_id)
#              new = {}
#              new["CodigoPedido"] = newc['Codigo']
#              new["CodigoArticulo"]= det.product_id.default_code
#              new["Unidades"] = int(det.product_uom_qty)
#              new["PesoDeclarado"]: 1
#              new["MinimoDiasVencimiento"]: 1
#              new["FechaVencimiento"]:  saleorder.validity_date.strftime('%Y-%m-%d %H:%M:%S')
           for picking in stock_pickings:
               picking.sudo().write({'codigo_wms':cod_pedido})
               if sp.carrier_id and picking.carrier_id != sp.carrier_id:
                   picking.carrier_id = sp.carrier_id.id
               for move in picking.move_ids_without_package:
                   move.write({'quantity_done': 0,'forecast_availability': 0 })
                   # Access product_id and product_uom_qty
                   product_code = move.product_id.default_code
                   quantity = move.product_uom_qty
                   # Accumulate quantities by product_code in the dictionary
                   product_dict[product_code] += quantity
           # Convert defaultdict to regular dict (if needed)
           product_dict = dict(product_dict)
           for key,value in product_dict.items():
              new = {}
              new["CodigoPedido"] = newc['Codigo']
              new["CodigoArticulo"]= key
              new["Unidades"] = int(value)
              new["PesoDeclarado"]: 1
              new["MinimoDiasVencimiento"]: 1
              _logger.info(new)
              # Antes de enviar a dipip, verifico si hay esto en digip
              #unidades = self.get_stock(new['CodigoArticulo'])
              #if self.get_stock(new['CodigoArticulo']) > 0:
              if new['CodigoArticulo'] in stock_codigos and stock_codigos[new['CodigoArticulo']]  > 0:
                  resp = requests.post('%s/v1/Pedidos/%s/Detalle' % (url,newc['Codigo']), headers=headers, json=new)
                  _logger.info(resp.content)
              else:
                 _logger.info('%s Sin Stock' % new['CodigoArticulo'])

           if respPost.status_code in [200,201]:
              sp.change_state_wms(cod_pedido,'done')
           else:
              sp.change_state_wms(cod_pedido,'error')
        return True

    def change_state_wms(self,cod_pedido,rta):
        pickings = self.env['stock.picking'].sudo().search([('codigo_wms','=',cod_pedido),('state','not in',['draft','cancel']),('state_wms','!=','done')])
        for picking in pickings:
            picking.sudo().write({'state_wms':rta})


    def recibir_todos(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        # Busco todos los pedidos enviados
        _logger.info('Busco pedidos ')
        recibidos={}
        # Leo todos los pedidos de Digip y me quedo con los que estan en estado 4
        respGet = requests.get('%s/v1/Pedidos' % (url), headers=headers)
        r = eval(respGet.content)
        for result in r:
            if result['PedidoEstado'] == 4:
                recibidos[result['Codigo']] = result['Codigo']
        for codigo_wms in recibidos:
            for picking in self.env['stock.picking'].sudo().search([('state','not in',['cancel']),('state_wms','=','done'),('codigo_wms','=',codigo_wms)]):
                picking.do_unreserve()
            for picking in self.env['stock.picking'].sudo().search([('state','not in',['cancel']),('state_wms','=','done'),('codigo_wms','=',codigo_wms)]):
                cod_pedido = picking.codigo_wms
                respGet = requests.get('%s/v1/Pedidos/%s' % (url,cod_pedido), headers=headers)
                if respGet.status_code in [200,201] and respGet.content.strip() != b'null':
                    result = eval(respGet.content)
                    if result['PedidoEstado'] == 4:
                        _logger.info('Recibiendo DIGIP WMS %s' % cod_pedido)
                        picking.recibir()
                        self.env.cr.commit()

    def recibir(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        # leo el detalle del pedido en digip
        if not self.sale_id:
            return False
        saleorder = self.env['sale.order'].sudo().search([('name','=',str(self.origin)),('state','in',['sale','done','cancel'])],limit=1)
        _logger.info(saleorder)
        if not saleorder:
            return False
        #cod_pedido = re.sub('/','_',saleorder.name)
        cod_pedido = self.codigo_wms
        # Controlo estado del pedido antes de recibir
        respGet = requests.get('%s/v1/Pedidos/%s' % (url,cod_pedido), headers=headers)
        if respGet.status_code in [200,201] and respGet.content.strip() != b'null':
            result = eval(respGet.content)
            _logger.info('%s' % result)
            if result['PedidoEstado'] != 4:
                raise ValidationError('El pedido no se encuentra en estado completo, por eso no se puede recibir.')

        respGet = requests.get('%s/v1/Pedidos/%s/Detalle' % (url,cod_pedido), headers=headers)
        _logger.info(respGet)
        if respGet.status_code in [200,201] and respGet.content.strip() != b'null':
            result = eval(respGet.content)
            _logger.info(result)
            pickings = self.env['stock.picking'].sudo().search([('codigo_wms','=',cod_pedido),('state','not in',['draft','done','cancel'])])
            # Traigo la cantidad de bultos pickiados en digip
            bultos = self.get_bultos(cod_pedido)
            _logger.info(pickings)
            # Marco las cantidades que traingo desde digip
            for picking in pickings:
               picking.sudo().write({'number_of_packages': bultos })
               for det in picking.move_ids_without_package:
                  det.write({'quantity_done': 0,'forecast_availability': 0 })
                  # Busco codigo en result
                  for r in result:
                     if r['UnidadesSatisfecha'] and r['Unidades']:
                        if r['CodigoArticulo'] == det.product_id.default_code:
                            ratio = det.product_uom_qty/r['Unidades']
                            _logger.info(' %s %s' % ( det.product_id.default_code , {'quantity_done': round(ratio*r['UnidadesSatisfecha'],0),'forecast_availability': round(ratio*r['UnidadesSatisfecha'],0) } ) )
                            det.write({'quantity_done': round(ratio*r['UnidadesSatisfecha'],0),'forecast_availability': round(ratio*r['UnidadesSatisfecha'],0) })
            self.write({'state_wms':'closed'})

#    def action_assign(self):
#        self.recibir()

    def recibir_recepcion(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        # leo el detalle del pedido en digip
        #cod_recepcion = re.sub('\/','_',self.name)
        sp = self
        cod_recepcion = self.codigo_wms
        if not sp.dispatch_number:
            raise UserError('Debe definar el numero de despacho para poder continuar')

        respGet = requests.get('%s/v1/ControlCiego?DocumentoNumero=%s' % (url,cod_recepcion), headers=headers)
        if respGet.status_code in [200,201] and respGet.content.strip() != b'null':
           respGet_json = respGet.json()
           _logger.info(('respGet',respGet_json))
           # Verifico que todos los codigos recibidos enten en el picking
           picking={}
           for move in self.move_ids_without_package:
               picking[move.product_id.default_code] = move.product_id.default_code
           for item in respGet_json["ControlCiegoDetalle"]:
               if item["CodigoArticulo"] not in picking:
                   raise ValidationError('El codigo %s no se encuentra en la pediro de recepcion, por favor agregue el codigo y vuelva a recibir' % item["CodigoArticulo"])

           for move in self.move_ids_without_package:
               u_recibidas = self.find_units_of_product(respGet_json,move.product_id.default_code)
               move.write({'quantity_done': u_recibidas})
           for lots in self.move_line_nosuggest_ids:
               lots.write({'lot_name': sp.dispatch_number + '_' + lots.product_id.default_code})
           # modifico el numero de despacho agregando pais y fecha de recepcion
           self.write({'dispatch_number':self.dispatch_number +' '+self.partner_id.country_id.name })
           self.write({'state_wms':'closed'})
        return True

    def enviar_recepcion(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        sp = self
        if (not sp.purchase_id or not sp.sale_id) and not sp.picking_type_code == 'incoming':
            return False
        # Verifico que todos los codigos tengan default code
        for move in self.move_ids_without_package:
            if move.product_id.default_code == None:
                raise ValidationError('El producto %s no esta completo' % move.product_id.name )

        cod_pedido = self.env['ir.sequence'].sudo().next_by_code('DIGIP_R')
        cod_pedido = '%s_%s' % (cod_pedido,sp.carrier_tracking_ref)
        sp.sudo().write({'codigo_wms':cod_pedido})
        _logger.info('CODIGO %s' % cod_pedido)
        respGet = requests.get('%s/v1/DocumentoRecepcion/%s' % (url,cod_pedido), headers=headers)
        _logger.info(respGet)
        _logger.info(respGet.content)
        if respGet.status_code not in [200,201] or respGet.content.strip() == b'null':
           self.create_update_proveedor(sp)
           data = {
              "Numero": cod_pedido,
              "Factura": re.sub(' ','',re.sub('/','_',sp.name))[:12],
              "Fecha": sp.create_date.strftime('%Y-%m-%d %H:%M:%S'),
              "CodigoProveedor": 'o'+str(sp.partner_id.id),
#              "Observacion": str(sp.note),
              "Observacion": "Container: " + sp.container,
              "DocumentoRecepcionTipo": "remito",
              "RecepcionTipo": "abastecimiento",
              "DocumentoRecepcionDetalleRequest": [],
           }
           for move in self.move_ids_without_package:
              self.create_update_articulo(move.product_id)
              move.write({'quantity_done': 0,'forecast_availability': 0 })
              move_data = {
                "CodigoArticulo": str(move.product_id.default_code),
#               "Lote": sp.dispatch_number + '_' + move.product_id.default_code,
#                "FechaVencimiento": sp.date_deadline.strftime('%Y-%m-%d %H:%M:%S'),
                "Unidades": str(int(move.product_uom_qty)),
              }
              data["DocumentoRecepcionDetalleRequest"].append(move_data)
           _logger.info(data)
           respPost = requests.post('%s/v1/DocumentoRecepcion' % (url), headers=headers, json=data)
           _logger.info(respPost)
           _logger.info(respPost.content)
        if respGet.status_code in [200,201] or respPost.status_code in [200,201]:
           sp.sudo().write({'state_wms':'done'})
        else:
           sp.sudo().write({'state_wms':'error'})
        return True

    def get_date(self,datetime_field):
        date_string = datetime_field
        if date_string:
            date_only_string = fields.Datetime.to_string(date_string)
            date_only = date_only_string.split()[0]
            return date_only
        else:
            return False


    def get_unidades_satisfechas(self,codigo,data):
        for item in data:
            for pedido in item.get('Pedidos', []):
                if pedido.get('Codigo') == codigo:
                    return pedido['PedidoDetalle'][0]['UnidadesSatisfecha']
        return None


    def find_units_of_product(self,response_json, product_code):
        total_units = 0
        # Parametros: restpuesta de ControlCiego y Codigo de Producto
        # Encontrar unidades de cada product_code en ControlCiegoDetalle
        for item in response_json["ControlCiegoDetalle"]:
            if item["CodigoArticulo"] == product_code:
                total_units += item["Unidades"]
        return total_units


    def button_validate(self):
        res = super(StockPicking, self).button_validate()
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        sp = self
        origin = str(sp.origin)
        # Check if the origin contains 'Retorno de ' and extract the return_origin
        if 'Retorno de ' in origin:
            return_origin = sp.origin.split('Retorno de ')[1]  # Get the part after 'Retorno de'
            _logger.info("Origen del retorno encontrado: %s", return_origin)
            # Look for a record in stock.picking with the extracted return_origin
            return_picking = self.env['stock.picking'].sudo().search([('name', '=', return_origin)], limit=1)
            if return_picking:
                origin = str(return_picking.origin)
                _logger.info("Encontrada la transferencia: %s con origen: %s", return_picking.name, return_picking.origin)
            else:
                _logger.warning("No se encuentra la transferencia con el nombre: %s", return_origin)

        if not sp.sale_id:
            return res
        if not sp.purchase_id:
            saleorder = sp.env['sale.order'].sudo().search([('name','=',str(origin)),('state','in',['sale','done','cancel'])],limit=1)
            _logger.info(('saleorder ',saleorder))
            self.control_remito_digip()
            if not saleorder:
                return False
            _logger.info(('codigo_wms',sp.codigo_wms))
            #cod_pedido = re.sub('/','_',saleorder.name)
            cod_pedido = sp.codigo_wms
            respPut = requests.put('%s/v1/Pedidos/%s/Remitido' % (url,cod_pedido), headers=headers)
            _logger.info(('respPut',respPut))
           #if respPut.status_code not in [200,201]:
           #    raise ValidationError('El pedido no se encuentra en estado completo, por eso no se puede marcar como remitido.')
        return res

    def fix_unreserve(self):
        quants = self.env["stock.quant"].search([])
        move_line_ids = []
        warning = ""

        for quant in quants:
            move_lines =self.env["stock.move.line"].search(
                [
                    ("product_id", "=", quant.product_id.id),
                    ("location_id", "=", quant.location_id.id),
                    ("lot_id", "=", quant.lot_id.id),
                    ("package_id", "=", quant.package_id.id),
                    ("owner_id", "=", quant.owner_id.id),
                    ("product_qty", "!=", 0),
                ]
            )
            move_line_ids += move_lines.ids
            reserved_on_move_lines = sum(move_lines.mapped("product_qty"))
            move_line_str = str.join(
                ", ", [str(move_line_id) for move_line_id in move_lines.ids]
            )
        
            if quant.location_id.should_bypass_reservation():
                # If a quant is in a location that should bypass the reservation, its `reserved_quantity` field
                # should be 0.
                if quant.reserved_quantity != 0:
                    quant.write({"reserved_quantity": 0})
            else:
                # If a quant is in a reservable location, its `reserved_quantity` should be exactly the sum
                # of the `product_qty` of all the partially_available / assigned move lines with the same
                # characteristics.
                if quant.reserved_quantity == 0:
                    if move_lines:
                        move_lines.with_context(bypass_reservation_update=True).write(
                            {"product_uom_qty": 0}
                        )
                elif quant.reserved_quantity < 0:
                    quant.write({"reserved_quantity": 0})
                    if move_lines:
                        move_lines.with_context(bypass_reservation_update=True).write(
                            {"product_uom_qty": 0}
                        )
                else:
                    if reserved_on_move_lines != quant.reserved_quantity:
                        move_lines.with_context(bypass_reservation_update=True).write(
                            {"product_uom_qty": 0}
                        )
                        quant.write({"reserved_quantity": 0})
                    else:
                        if any(move_line.product_qty < 0 for move_line in move_lines):
                            move_lines.with_context(bypass_reservation_update=True).write(
                                {"product_uom_qty": 0}
                            )
                            quant.write({"reserved_quantity": 0})
        move_lines = self.env["stock.move.line"].search(
            [
                ("product_id.type", "=", "product"),
                ("product_qty", "!=", 0),
                ("id", "not in", move_line_ids),
            ]
        )

        move_lines_to_unreserve = []

        for move_line in move_lines:
            if not move_line.location_id.should_bypass_reservation():
                move_lines_to_unreserve.append(move_line.id)

        if len(move_lines_to_unreserve) > 1:
            self.env.cr.execute(
                """ 
                    UPDATE stock_move_line SET product_uom_qty = 0, product_qty = 0 WHERE id in %s ;
                """
                % (tuple(move_lines_to_unreserve),)
            )

        elif len(move_lines_to_unreserve) == 1:
            self.env.cr.execute(
                """ 
                UPDATE stock_move_line SET product_uom_qty = 0, product_qty = 0 WHERE id = %s ;
                """
                % (move_lines_to_unreserve[0])
            )


    def action_cancel(self):
        result = super(StockPicking, self).action_cancel()
        for rec in self:
            picking = []
            if rec.sale_id:
               picking = rec.env['stock.picking'].sudo().search([('sale_id','=',rec.sale_id.id),('state','not in',['draft','cancel','done']),('sale_id.state','in',['done','sale'])])
            elif rec.purchase_id:
               picking = rec.env['stock.picking'].sudo().search([('purchase_id','=',rec.purchase_id.id),('state','not in',['draft','cancel','done']),('purchase_id.state','in',['done','purchase'])])

            if not picking or len(picking)<1:
                if rec.purchase_id and rec.purchase_id.cancelling:
                    return result
                if rec.sale_id and rec.sale_id.cancelling:
                    return result
                raise UserError('No puede cancelar un pedido que no tiene ACOPIO')
            else:
               for line in rec.move_ids_without_package:
                   picking0 = False
                   for pick in picking:
                       picking_line = rec.env['stock.move'].sudo().search([('picking_id','=',pick.id),('picking_id.state','not in',['cancel','done']),
                                                                           ('purchase_line_id','=',line.purchase_line_id.id)])
                       picking0 = pick
                       if picking_line:
                           break

                   if picking_line:
                       picking_line.product_uom_qty = picking_line.product_uom_qty + line.quantity_done
                       picking_line.forecast_availability = picking_line.product_uom_qty + line.quantity_done
                   else:
                       rec.env['stock.move'].create({'purchase_line_id': line.purchase_line_id.id, 'product_id': line.product_id.id, 'company_id': line.company_id.id, 'product_uom_qty': line.product_uom_qty,
                                           'date': line.date, 'location_id': picking0.location_id.id, 'location_dest_id': picking0.location_dest_id.id, 'name': picking0.name,
                                           'procure_method': line.procure_method, 'product_uom': line.product_uom.id, 'picking_id': picking0.id, 'state':'assigned', 'group_id': rec.group_id.id})
                       picking0.sudo().write({'state':'assigned','group_id': rec.group_id.id})
                       picking0.action_confirm()
        return result
    def control_remito_digip(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        # leo el detalle del pedido en digip
        if not self.sale_id:
            return False
        saleorder = self.env['sale.order'].sudo().search([('name','=',str(self.origin)),('state','in',['sale','done','cancel'])],limit=1)
        if not saleorder:
            return False
        #cod_pedido = re.sub('/','_',saleorder.name)
        cod_pedido = self.codigo_wms
        # Controlo estado del pedido antes de recibir
        respGet = requests.get('%s/v1/Pedidos/%s' % (url,cod_pedido), headers=headers)
        if respGet.status_code in [200,201] and respGet.content.strip() != b'null':
            result = eval(respGet.content)
            _logger.info('%s' % result)

        respGet = requests.get('%s/v1/Pedidos/%s/Detalle' % (url,cod_pedido), headers=headers)
        if respGet.status_code in [200,201] and respGet.content.strip() != b'null':
            result = eval(respGet.content)
            pickings = self.env['stock.picking'].sudo().search([('codigo_wms','=',cod_pedido)])
            # Traigo la cantidad de bultos pickiados en digip
            product_dict = defaultdict(float)
            for picking in pickings:
                picking.sudo().write({'codigo_wms':cod_pedido})
                for move in picking.move_ids_without_package:
                    # Access product_id and product_uom_qty
                    product_code = move.product_id.default_code
                    #quantity = move.product_uom_qty
                    quantity = move.quantity_done
                    # Accumulate quantities by product_code in the dictionary
                    product_dict[product_code] += quantity
            errores = []
            # Marco las cantidades que traingo desde digip
            for picking in pickings:
                con_diferencia = False
                for det in picking.move_ids_without_package:
                  # Busco codigo en result
                    line = '%s %s %s' % (picking.codigo_wms,det.product_id.default_code,det.quantity_done)
                    cantidad_digip  = 0
                    ratio = 0
                    for r in result:
                        if r['UnidadesSatisfecha'] and r['Unidades']:
                            if r['CodigoArticulo'] == det.product_id.default_code:
                                #ratio =  det.product_uom_qty / product_dict[det.product_id.default_code] 
                                if  product_dict[det.product_id.default_code] > 0:
                                    ratio =  det.quantity_done / product_dict[det.product_id.default_code] 
                                else:
                                    ratio = 1
                                cantidad_digip = round(r['UnidadesSatisfecha']  * ratio,0)
                    if (det.quantity_done-cantidad_digip) != 0:
                        con_diferencia = True
                        errores.append('%s Digip %s Local %s' % (det.product_id.default_code,cantidad_digip,det.quantity_done) )
                if con_diferencia:
                    raise ValidationError('El pedidos tiene diferencias en DIGIP %s Diferencias: %s' % (cod_pedido,errores) )
                            

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    cancelling = fields.Boolean('Cancelar PO', copy=False)

    def action_cancel(self):
        for rec in self:
            if rec.state in ['purchase','done']:
                rec.cancelling = True
        return super(SaleOrder, self).action_cancel()

    def action_draft(self):
        for rec in self:
            if rec.state in ['cancel']:
                rec.cancelling = False
        return super(SaleOrder, self).action_draft()




class SaleOrder(models.Model):
    _inherit = 'sale.order'

    cancelling = fields.Boolean('Cancelar SO', copy=False)

    def action_cancel(self):
        for rec in self:
            if rec.state in ['sale','done']:
                rec.cancelling = True
        return super(SaleOrder, self).action_cancel()

    def action_draft(self):
        for rec in self:
            if rec.state in ['cancel']:
                rec.cancelling = False
        return super(SaleOrder, self).action_draft()
