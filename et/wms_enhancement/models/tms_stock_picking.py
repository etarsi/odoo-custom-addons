from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class TmsStockPicking(models.Model):
    _inherit = 'tms.stock.picking'
    _description = 'Ruteo Stock Picking'
    
    #agregar campo relacionado con wms_task
    wms_task_id = fields.Many2one('wms.task', string='Tarea WMS', ondelete='set null', index=True, tracking=True)
    bulk_defendant = fields.Float(string="Bultos Demandados", tracking=True, compute="_compute_bulk_defendant", store=True)
    bulk_picking = fields.Float(string="Bultos Pickeados", tracking=True, compute="_compute_bulk_picking", store=True)
    
    @api.depends("wms_task_id", "wms_task_id.bultos_count")
    def _compute_bulk_defendant(self):
        for rec in self:
            if rec.wms_task_id:
                rec.bulk_defendant = rec.wms_task_id.bultos_count
            else:
                rec.bulk_defendant = 0

    @api.depends("wms_task_id", "wms_task_id.bultos_prepared")
    def _compute_bulk_picking(self):
        for rec in self:
            if rec.wms_task_id:
                rec.bulk_picking = rec.wms_task_id.bultos_prepared
            else:
                rec.bulk_picking = 0

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
    wms_task_ids = fields.Many2many('wms.task', string='Tareas WMS', compute="_compute_wms_task_ids", store=False)
    
    
    @api.depends('road_maps_line_ids.wms_task_id')
    def _compute_wms_task_ids(self):
        for rec in self:
            rec.wms_task_ids = rec.mapped('road_maps_line_ids.wms_task_id')
            
    def action_wms_task_tree_view(self):
        self.ensure_one()
        wms_tasks = self.mapped('road_maps_line_ids.wms_task_id')
        if not wms_tasks:
            raise ValidationError("No hay tareas WMS asociadas a esta Hoja de Ruta.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Tareas WMS',
            'res_model': 'wms.task',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', wms_tasks.ids)],
            'target': 'current',
        }

class TmsRoadmapLine(models.Model):
    _inherit = 'tms.roadmap.line'
    _description = 'Linea de la Hoja de Ruta'
    
    #agregar campo relacionado con wms_task
    wms_task_id = fields.Many2one('wms.task', string='Tarea WMS', ondelete='set null', index=True, tracking=True)