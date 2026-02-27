from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class TmsStockPicking(models.Model):
    _inherit = 'tms.stock.picking'
    _description = 'Ruteo Stock Picking'
    
    #agregar campo relacionado con wms_task
    wms_task_id = fields.Many2one('wms.task', string='Tarea WMS', ondelete='set null', index=True, tracking=True)
    
    
class TmsRoadmap(models.Model):
    _inherit = 'tms.roadmap'
    _description = 'Hoja de Ruta'
    
    #agregar campo relacionado con wms_task
    wms_task_id = fields.Many2one('wms.task', string='Tarea WMS', ondelete='set null', index=True, tracking=True)