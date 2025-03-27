from odoo import tools, models, fields, api, _
import requests
from requests.structures import CaseInsensitiveDict

class DigipWMS:
    def __init__(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')

    def create_update_articulo(self,p):
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
        resp = requests.post('%s/v1/Articulos' % url, headers=headers, json=new)
        return True

    def send_stock_picking(self,sp):
        # Busco los envios pendiente que tiene el documento de origen de la SO
        # Genero un solo documento do SO
    
        # Envio cabecera
        newc={}
        newc["Codigo"]= sp.name
        newc["CodigoClienteUbicacion"]= sp.partner.ref
        newc["PedidoEstado"]= "pendiente"
        newc["Fecha"]= sp.create_date
        newc["FechaEstimadaEntrega"]= sp.scheduler_date
        newc["Observacion"]= sp.origin
        newc["Importe"]= "100"
        newc["CodigoDespacho"]= "string"
        newc["CodigoDeEnvio"]= "string"
        newc["ServicioDeEnvioTipo"]= "propio"
        newc["PedidoTag"]= ["string"]
        resp = requests.post('%s/v1/Pedidos/%s' % (url,newc['Codigo']), headers=headers, json=new)
        # Envio detalle
        # Busco los codigos pendientes, y los pongo todos juntos, para enviarlos de una sola vez
        for det in sp.move_line_ids:
            new = {}
            new["CodigoPedido"] = sp.name
            new["CodigoArticulo"]= det.product_id.default_code
            new["Unidades"] = det.product_uom_qty
            new["PesoDeclarado"]: 1
            new["MinimoDiasVencimiento"]: 1
            new["FechaVencimiento"]:  sp.scheduler_date
            resp = requests.post('%s/v1/Pedidos/%s/Detalle/%s' % (url,newc['Codigo'],new['CodigoPedido']), headers=headers, json=new)

    def read_picking_uom(self,sp):
        # leo el detalle del pedido en digip
        resp = requests.get('%s/v1/Pedidos/%s/Detalle' % (url,sp.name), headers=headers) 
        if resp:
            result = eval(resp)
            # Marco las cantidades que traingo desde digip
            for det in sp.move_lines_ids:
                # Busco codigo en result
                for r in result:
                    if r['CodigoArticulo'] == det.product_id.default_code:
                        det.write({'quantity_done': r['UnidadesSatisfecha']})
        return True