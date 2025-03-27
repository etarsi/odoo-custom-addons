from odoo import tools, models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import requests
from requests.structures import CaseInsensitiveDict
import re
from collections import defaultdict
null=None

_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = "stock.picking"

    state_wms = fields.Selection([('closed','Enviado y recibido'),('done','Enviado'),('no','No enviado'),('error','Error envio')],string='Estado WMS',default='no')
    container = fields.Char(string='Container',copy=False)


    def send_incoming(self):
        return True


    def create_update_cliente(self,p):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get('%s/v1/Clientes/%s' % (url,'o'+str(p.partner_id.id)), headers=headers)
        _logger.info(('---GET----cliente--->',respGet))
        if respGet.status_code not in [200,201] or respGet.content.strip() == b'null':
          new = {}
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

    def create_update_ubicacion(self,p):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get('%s/v1/Clientes/%s/ClientesUbicaciones' % (url,'u'+str(p.partner_id.id)), headers=headers)
        _logger.info(('---GET--create ubicacion----->',respGet))
        if respGet.status_code != 200 and respGet.status_code != 201:
          new = {}
          new["Codigo"]= 'u' + str(p.partner_id.id)
          new["Descripcion"]= p.partner_id.name
          new["Direccion"]= str(p.partner_id.street)
          if p.partner_id.street2:
             new["Direccion"] += ' ' + str(p.partner_id.street2)
          new["Localidad"]= p.partner_id.city
          new["Email"]= p.partner_id.email
          if p.partner_id.state_id:
             new["Provincia"]= p.partner_id.state_id.name
          new["Activo"]= p.partner_id.active
          respPost = requests.post('%s/v1/Cliente/%s/ClientesUbicaciones' % (url,'o'+str(p.partner_id.id)), headers=headers, json=new)
          _logger.info(('----POST----ubicacion-->',respPost))
        return True


    def create_update_articulo(self,p):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        respGet = requests.get('%s/v1/Articulos/%s' % (url,str(p.default_code)), headers=headers)
        _logger.info(('---GET------->',respGet))
        if respGet.status_code != 200 and respGet.status_code != 201:
           new = {}
           new["CodigoArticulo"]= p.default_code
           new["Descripcion"]= p.name
           new["DiasVidaUtil"]= 9999
           new["UsaLote"]= True
           new["UsaSerie"]= False
           new["UsaVencimiento"]= False
           new["EsVirtual"]= False
           new["ArticuloTipoRotacion"]= "alta"
           new["Activo"]= True
           new["UsaPesoDeclarado"]= False
           new["PesoDeclaradoPromedio"]= 0
           respPost = requests.post('%s/v1/Articulos' % url, headers=headers, json=new)
        return True

#    @api.model
#    def create(self, vals):
#        res = super(StockPicking, self).create(vals)
#        if res.state not in ['done'] and res.picking_type_code =='outgoing':
#            try:
#                res.enviar()
#            except:
#                pass
#        return res


    def enviar(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        # Busco los envios pendiente que tiene el documento de origen de la SO
        # Genero un solo documento do SO
        # Envio cabecera
        sp = self
        #cod_pedido = re.sub('/','_',sp.name)
        if not sp.picking_type_code =='outgoing' or not sp.origin:
            return False
        product_dict = defaultdict(float)
        saleorder = sp.env['sale.order'].sudo().search([('name','=',str(sp.origin)[:6]),('state','in',['sale','done','cancel'])],limit=1)
        if not saleorder:
            return False
        cod_pedido = re.sub('/','_',saleorder.name)
        stock_pickings = sp.env['stock.picking'].sudo().search([('origin', 'ilike', str(saleorder.name)),('state','not in',['draft','done','cancel'])])
        _logger.info(stock_pickings)
        if not stock_pickings:
            return False
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
           newc["Observacion"]= str(sp.note)
           newc["Importe"]= str(saleorder.amount_total)
           newc["CodigoDespacho"]= str(sp.carrier_id.name) if sp.carrier_id else "string"
           newc["CodigoDeEnvio"]= "string"
           newc["ServicioDeEnvioTipo"]= "propio"
           newc["PedidoTag"]= ["string"]
           respPost = requests.post('%s/v1/Pedidos' % (url), headers=headers, json=newc)
           _logger.info(respPost.content)
           # Envio detalle
           # Busco los codigos pendientes, y los pongo todos juntos, para enviarlos de una sola vez
           #for det in sp.move_ids_without_package:
#           for det in saleorder.order_line:
#              self.create_update_articulo(det.product_id)
#              new = {}
#              new["CodigoPedido"] = newc['Codigo']
#              new["CodigoArticulo"]= det.product_id.default_code
#              new["Unidades"] = int(det.product_uom_qty)
#              new["PesoDeclarado"]: 1
#              new["MinimoDiasVencimiento"]: 1
#              new["FechaVencimiento"]:  saleorder.validity_date.strftime('%Y-%m-%d %H:%M:%S')
           for picking in stock_pickings:
               if sp.carrier_id and picking.carrier_id != sp.carrier_id:
                   picking.carrier_id = sp.carrier_id.id
               for move in picking.move_ids_without_package:
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
              resp = requests.post('%s/v1/Pedidos/%s/Detalle' % (url,newc['Codigo']), headers=headers, json=new)
              _logger.info(resp.content)

           if respPost.status_code in [200,201]:
              sp.change_state_wms(saleorder,'done')
           else:
              sp.change_state_wms(saleorder,'error')
        return True




    def change_state_wms(self,saleorder,rta):
        pickings = self.env['stock.picking'].sudo().search([('origin','ilike',saleorder.name),('state','not in',['draft','cancel']),('state_wms','!=','done')])
        for picking in pickings:
            picking.sudo().write({'state_wms':rta})


    def recibir(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        # leo el detalle del pedido en digip
        if not self.sale_id:
            return False
        saleorder = self.env['sale.order'].sudo().search([('name','=',str(self.sale_id.origin)),('state','in',['sale','done','cancel'])],limit=1)
        _logger.info(saleorder)
        if not saleorder:
            return False
        cod_pedido = re.sub('/','_',saleorder.name)
        respGet = requests.get('%s/v1/Pedidos/%s/Detalle' % (url,cod_pedido), headers=headers)
        _logger.info(respGet)
        if respGet.status_code in [200,201] and respGet.content.strip() != b'null':
            result = eval(respGet.content)
            _logger.info(result)
            pickings = self.env['stock.picking'].sudo().search([('sale_id.origin','=',cod_pedido),('state','not in',['draft','done','cancel'])])
            _logger.info(pickings)
            # Marco las cantidades que traingo desde digip
            for picking in pickings:
               for det in picking.move_ids_without_package:
                  # Busco codigo en result
                  for r in result:
                     if r['UnidadesSatisfecha'] and r['Unidades']:
                        if r['CodigoArticulo'] == det.product_id.default_code:
                            ratio = det.product_uom_qty/r['Unidades']
                            det.write({'quantity_done': round(ratio*r['UnidadesSatisfecha'],0),'forecast_availability': round(ratio*r['UnidadesSatisfecha'],0) })
               for det in picking.move_line_ids_without_package:
                  # Busco codigo en result
                  for r in result:
                     if r['UnidadesSatisfecha'] and r['Unidades']:
                        if r['CodigoArticulo'] == det.product_id.default_code:
                            det.write({'product_uom_qty': det.qty_done})
            self.write({'state_wms':'closed'})
        return True

    def action_assign(self):
        self.recibir()

    def recibir_recepcion(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        # leo el detalle del pedido en digip
        cod_recepcion = re.sub('\/','_',self.name)
        respGet = requests.get('%s/v1/ControlCiego?DocumentoNumero=%s' % (url,cod_recepcion), headers=headers)
        if respGet.status_code in [200,201] and respGet.content.strip() != b'null':
           respGet_json = respGet.json()
           _logger.info(('respGet',respGet_json))
           for move in self.move_ids_without_package:
               u_recibidas = self.find_units_of_product(respGet_json,move.product_id.default_code)
               if u_recibidas > 0:
                   move.write({'quantity_done': u_recibidas})
           self.write({'state_wms':'closed'})
        return True

    def enviar_recepcion(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        sp = self
        cod_pedido = re.sub('/','_',sp.name)
        if not sp.purchase_id:
            return False
        respGet = requests.get('%s/v1/DocumentoRecepcion/%s' % (url,cod_pedido), headers=headers)
        _logger.info(respGet)
        if respGet.status_code not in [200,201] or respGet.content.strip() == b'null':
           self.create_update_proveedor(sp)
           data = {
              "Numero": cod_pedido,
              "Factura": str(sp.carrier_tracking_ref)[:12],
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
              move_data = {
                "CodigoArticulo": str(move.product_id.default_code),
                "Lote": sp.carrier_tracking_ref,
#                "FechaVencimiento": sp.date_deadline.strftime('%Y-%m-%d %H:%M:%S'),
                "Unidades": str(int(move.product_uom_qty)),
              }
              data["DocumentoRecepcionDetalleRequest"].append(move_data)
           _logger.info(data)
           respPost = requests.post('%s/v1/DocumentoRecepcion' % (url), headers=headers, json=data)
           _logger.info(respPost)
        if respGet.status_code in [200,201] or respPost.status_code in [200,201]:
           sp.sudo().write({'state_wms':'done'})
        else:
           sp.sudo().write({'state_wms':'error'})
        return True

    def get_date(self,datetime_field):
        date_string = datetime_field
        if date_string:
            # Convert DateTime field to string
            date_only_string = fields.Datetime.to_string(date_string)
            # Extract date part
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
        if not sp.sale_id:
            return res
        if not sp.purchase_id:
            saleorder = sp.env['sale.order'].sudo().search([('name','=',str(sp.sale_id.origin)),('state','in',['sale','done','cancel'])],limit=1)
            if not saleorder:
                return False
            cod_pedido = re.sub('/','_',saleorder.name)
            respPut = requests.put('%s/v1/Pedidos/%s/Remitido' % (url,cod_pedido), headers=headers)
#            if respPut.status_code not in [200,201]:
#                raise ValidationError('El pedido no se encuentra en estado completo, por eso no se puede marcar como remitido.')
        return res


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
