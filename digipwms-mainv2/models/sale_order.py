from odoo import tools, models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
import requests
from requests.structures import CaseInsensitiveDict
import re
null=None

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = "sale.order"

    def enviar(self):
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
        headers = CaseInsensitiveDict()
        headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        sp = self
        if not sp.sale_id:
            return False
        saleorder = sp.env['sale.order'].sudo().search([('name','=',str(sp.sale_id.origin)),('state','in',['sale','done','cancel'])],limit=1)
        if not saleorder:
            return False
        cod_pedido = re.sub('/','_',saleorder.name)
        respGet = requests.get('%s/v1/Pedidos/%s' % (url,cod_pedido), headers=headers)
        if respGet.status_code not in [200,201] or respGet.content.strip() == b'null':
           self.create_update_cliente(sp)
           self.create_update_ubicacion(sp)
           newc={}
           newc["Codigo"]= cod_pedido
           newc["CodigoClienteUbicacion"]= sp.partner_id.id
           newc["PedidoEstado"]= "pendiente"
           newc["Fecha"]= sp.create_date.strftime('%Y-%m-%d %H:%M:%S')
           newc["FechaEstimadaEntrega"]= sp.scheduled_date.strftime('%Y-%m-%d %H:%M:%S')
           newc["Observacion"]= str(sp.note)
           newc["Importe"]= str(saleorder.amount_total)
           newc["CodigoDespacho"]= "string"
           newc["CodigoDeEnvio"]= "string"
           newc["ServicioDeEnvioTipo"]= "propio"
           newc["PedidoTag"]= ["string"]
