from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging
_logger = logging.getLogger(__name__)


class TmsRoadmap(models.Model):
    _inherit = 'tms.roadmap'
    _description = 'Hoja de Ruta'
    
    #agregar campo relacionado con wms_task
    wms_task_ids = fields.Many2many('wms.task', string='Tareas WMS', compute="_compute_wms_tasks", store=False)
    wms_task_count = fields.Integer(string="Cantidad de Tareas WMS", compute="_compute_wms_tasks", store=False)
    
    
    @api.depends("road_maps_line_ids.wms_task_id")
    def _compute_wms_tasks(self):
        for rec in self:
            tasks = rec.road_maps_line_ids.mapped("wms_task_id")  # recordset
            rec.wms_task_ids = tasks
            rec.wms_task_count = len(tasks)


    def action_open_wms_tasks(self):
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

    def action_print_roadmap(self):
        self.ensure_one()
        #abrir wizard tms_roadmap_report_wizard
        return {
            'type': 'ir.actions.act_window',
            'name': 'Imprimir Hoja de Ruta',
            'res_model': 'tms.roadmap.report.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_tms_roadmap_id': self.id,
            }
        }

class TmsRoadmapLine(models.Model):
    _inherit = 'tms.roadmap.line'
    _description = 'Linea de la Hoja de Ruta'
    
    #agregar campo relacionado con wms_task
    wms_task_id = fields.Many2one('wms.task', string='Tarea WMS', ondelete='set null', index=True, tracking=True)
    
    
    @api.onchange("tms_stock_picking_id")
    def _onchange_wms_task_id(self):
        for rec in self:
            if rec.tms_stock_picking_id:
                rec.wms_task_id = rec.tms_stock_picking_id.wms_task_id if rec.tms_stock_picking_id.wms_task_id else False
                rec.partner_id = rec.tms_stock_picking_id.partner_id if rec.tms_stock_picking_id.partner_id else False
                rec.direction = getattr(rec.tms_stock_picking_id, "direccion_entrega", False) or getattr(rec.tms_stock_picking_id, "direction", False)
                rec.industry_id = rec.tms_stock_picking_id.industry_id if rec.tms_stock_picking_id.industry_id else False
                rec.bulk_defendant = getattr(rec.tms_stock_picking_id, "bulk_defendant", 0.0) or 0.0
                rec.bulk_picking = getattr(rec.tms_stock_picking_id, "bulk_picking", 0.0) or 0.0