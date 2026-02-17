from odoo import models, fields, api


class WMSTask(models.Model):
    _name = 'wms.task'

    name = fields.Char()    
    state_preparation = fields.Selection(string="Estado", selection=[
        ('no', 'No aplica'),
        ('pending', 'Pendiente'),
        ('preparation', 'En Preparación'),
        ('control', 'Control'),
        ('delivery', 'Entregado'),
        ('cancel', 'Cancelado'),
    ])
    state_reception = fields.Selection(string="Estado", selection=[
        ('no', 'No aplica'),
        ('pending', 'Pendiente'),
        ('inprocess', 'En Proceso'),
        ('received', 'Ingresado'),
        ('cancel', 'Cancelado'),
    ])
    state_return = fields.Selection(string="Estado", selection=[
        ('no', 'No aplica'),
        ('pending', 'Pendiente'),
        ('inprocess', 'En Proceso'),
        ('control', 'Control'),
        ('cancel', 'Cancelado'),
    ])
    state_reception = fields.Selection(string="Estado", selection=[
        ('no', 'No aplica'),
        ('pending', 'Pendiente'),
        ('control', 'Control'),
        ('complete', 'Completado'),
        ('cancel', 'Cancelado'),
    ])
    type = fields.Selection(string="Tipo", selection=[
        ('reception', 'Recepción'),
        ('preparation', 'Preparación'),
        ('return', 'Devolución'),
        ('undo', 'Desarmar'),
        ('fraction', 'Fraccionado'),
        ('replenish', 'Reposición'),
        ('relocate', 'Reubicación')
    ])
    priority = fields.Integer(string="Prioridad")
    assigned_user_id = fields.Many2one(string="Asignado a", comodel_name="res.users")
    task_line_ids = fields.One2many(string="Líneas de Tarea", comodel_name="wms.task.line", inverse_name="task_id")
    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")
    partner_id = fields.Many2one(string="Contacto", rcomodel_name="res.partner")

    ## recepcion

    container = fields.Char(string="Contenedor")
    dispatch = fields.Char(string="N° Despacho")
    license = fields.Char(string="Licencia")

    # preparation




    ## statistics

    percent_complete = fields.Float()

    # category_ids = fields.One2many()

    bultos_count = fields.Float()


    # scheduled_at = fields.Datetime()
    started_at = fields.Datetime(string="Inicio")
    done_at = fields.Datetime(string="Fin")


    def action_confirm(self):
        for record in self:

            if record.type == 'return':
                
                lines_to_relocate = []
                lines_to_scrap = []

                for line in record.line_ids:
                    if line.is_broken:
                        lines_to_scrap.append(line.product_id)

                task_vals = {
                    'type':'relocate',
                    'priority':1,
                    'transfer_id':record.transfer_id.id,
                    
                }


                if lines_to_scrap:
                    self.env['wms.task'].create(task_vals)


class WMSTaskLine(models.Model):
    _name = 'wms.task.line'

    name = fields.Char()
    task_id = fields.Many2one(string="Tarea", comodel_name="wms.task")
    transfer_line_id = fields.Many2one(string="Línea de Transferencia", comodel_name="wms.transfer.line")
    product_id = fields.Many2one(string="Producto", comodel_name="product.product")
    quantity = fields.Integer(string="Demanda")
    quantity_picked = fields.Integer(string="Cantidad pickeada")
    quantity_controlled = fields.Integer(string="Cantidad Controlada")

    is_broken = fields.Boolean(string="¿Está roto?")