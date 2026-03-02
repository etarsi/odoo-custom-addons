from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class TmsStockPicking(models.Model):
    _inherit = 'tms.stock.picking'
    _description = 'Ruteo Stock Picking'
    
    #agregar campo relacionado con wms_task
    wms_task_id = fields.Many2one('wms.task', string='Tarea WMS', ondelete='set null', index=True, tracking=True)
    
    
    def action_open_wms_task(self):
        self.ensure_one()
        if not self.wms_task_id:
            raise ValidationError("No se ha asignado una tarea WMS a este Ruteo.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tarea WMS',
            'res_model': 'wms.task',
            'view_mode': 'form',
            'res_id': self.wms_task_id.id,
            'target': 'current',
        }
    
class TmsRoadmap(models.Model):
    _inherit = 'tms.roadmap'
    _description = 'Hoja de Ruta'
    
    #agregar campo relacionado con wms_task
    wms_task_id = fields.Many2one('wms.task', string='Tarea WMS', ondelete='set null', index=True, tracking=True)

    def action_open_wms_task(self):
        self.ensure_one()
        if not self.wms_task_id:
            raise ValidationError("No se ha asignado una tarea WMS a esta Hoja de Ruta.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tarea WMS',
            'res_model': 'wms.task',
            'view_mode': 'form',
            'res_id': self.wms_task_id.id,
            'target': 'current',
        }