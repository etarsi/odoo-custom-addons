from odoo import models, fields, api


class WMSTask(models.Model):
    _name = 'wms.task'

    name = fields.Char()    
    state = fields.Selection(string="Estado", selection=[
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('confirmed', )
    ])
    type = fields.Selection(string="Tipo", selection=[
        ('reception', 'Recepción'),
        ('preparation', 'Preparación'),
        ('control', 'Control'),
        ('undo', 'Desarmar'),
        ('fraction', 'Fraccionado'),
        ('replenish', 'Reposición')
    ])
    priority = fields.Integer(string="Prioridad")
    assigned_user_id = fields.Many2one(string="Asignado a", comodel_name="res.users")
    task_line_ids = fields.One2many(string="Líneas de Tarea", comodel_name="wms.task.line", inverse_name="task_id")
    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")


    ## recepcion

    provider_id = fields.Many2one(string="Proveedor", comodel_name="res.partner")
    container = fields.Char(string="Contenedor")
    dispatch = fields.Char(string="N° Despacho")
    license = fields.Char(string="Licencia")

    # preparation

    client_id = fields.Many2one(string="Cliente", comodel_name="res.partner")



    ## statistics

    percent_complete = fields.Float()

    category_ids = fields.One2many()

    bultos_count = fields.Float()


    # scheduled_at = fields.Datetime()
    started_at = fields.Datetime(string="Inicio")
    done_at = fields.Datetime(string="Fin")



class WMSTaskLine(models.Model):
    _name = 'wms.task.line'

    name = fields.Char()
    task_id = fields.Many2one(string="Tarea", comodel_name="wms.task")
    product_id = fields.Many2one(string="Producto", comodel_name="product.product")
    quantity = fields.Integer(string="Demanda")
    quantity_picked = fields.Integer(string="Cantidad pickeada")
    quantity_controlled = fields.Integer(string="Cantidad Controlada")