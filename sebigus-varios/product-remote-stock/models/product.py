from odoo import tools, models, fields, api, _
import base64
import logging
import requests
from requests.structures import CaseInsensitiveDict
_logger = logging.getLogger(__name__)

class RemoteStock(models.Model):
    _inherit = "product.template"
    remote_stock = fields.Integer(string='Cantidad Remota')
        
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
                codigos[j['CodigoArticulo']] =  j['UnidadesDisponibles']  + j['UnidadesReservadas']
        return codigos
    def update_remote_stock(self):
        stock_codigo = self.get_stocks()
        for p in self.env['product.template'].search([]):
            if p.default_code in stock_codigo:
                _logger.info('remote %s %s '  % (p.default_code,stock_codigo[p.default_code]) )
                p.write({'remote_stock':stock_codigo[p.default_code] } )


