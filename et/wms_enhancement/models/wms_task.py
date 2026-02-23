from odoo import models, fields, api, _
import requests
from odoo.exceptions import UserError


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
    partner_id = fields.Many2one(string="Contacto", comodel_name="res.partner")
    partner_address_id = fields.Many2one(string="Dirección de Entrega", comodel_name="res.partner")
    origin = fields.Char(string="Documento")
    digip_state = fields.Selection(string="Digip", selection=[
        ('no', 'No enviado'),
        ('sent', 'Enviado'),
        ('received', 'Recibido')
    ])

    ## recepcion

    container = fields.Char(string="Contenedor")
    dispatch = fields.Char(string="N° Despacho")
    license = fields.Char(string="Licencia")

    # preparation


    ## statistics

    percent_complete = fields.Float(string="Completado %")

    # category_ids = fields.One2many()

    bultos_count = fields.Float()


    # scheduled_at = fields.Datetime()
    started_at = fields.Datetime(string="Inicio")
    done_at = fields.Datetime(string="Fin")
    preparation_time = fields.Datetime(string="Tiempo de Preparación")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') in (False, 'New', '/'):
            vals['name'] = self.env['ir.sequence'].next_by_code('wms.task') or 'New'

        transfer_id = vals.get('transfer_id')
        if transfer_id and 'origin' in self._fields and not vals.get('origin'):
            transfer = self.env['wms.transfer'].browse(transfer_id)
            if transfer.exists():
                vals['origin'] = transfer.origin


        return super().create(vals)


    def action_open_wms_transfer(self):
        self.ensure_one()
        if not self.transfer_id:
           return False

        return {
           'type': 'ir.actions.act_window',
           'name': _('Transferencia WMS'),
           'res_model': 'wms.transfer',
           'view_mode': 'form',
           'res_id': self.transfer_id.id,
           'target': 'current',
        }
    
    def action_send_task_to_digip(self):    
        for record in self:
            
            task = {
                "codigo": record.name,
                "clienteUbicacionCodigo": "u"+str(record.partner_id.id),
                "fecha": str(fields.Date.context_today(self)),
                "estado": "Pendiente",
                "observacion": record.name,
                "servicioDeEnvioTipo": "Propio",
                "codigoDeEnvio": record.transfer_id.sale_id.name or "",
            }

            product_list = record.get_product_list()

            task["items"] = product_list

            posted = record.post_digip(task)

            if posted:
                record.digip_state = 'sent'



    def get_product_list(self):
        for record in self:
            product_list = []
            if record.task_line_ids:
                for line in record.task_line_ids:
                    product_info = {}
                    product_info['articuloCodigo'] = str(line.product_id.default_code)
                    product_info['unidades'] = line.quantity
                    product_info['linea'] = ""
                    product_info['lote'] = None
                    product_info['fechaVencimiento'] = None
                    product_info['minimoDiasVencimiento'] = 0

                    product_list.append(product_info)

            return product_list
        

    def post_digip(self, task):
        headers = {}
        url = self.env['ir.config_parameter'].sudo().get_param('digipwms-v2.url')
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')        
        response = requests.post(f'{url}/v2/Pedidos', headers=headers, json=task)

        if response.status_code == 201:
            return True
        else:
            raise UserError(f'Error al enviar a Digip la tarea. ERROR_CODE: {response.status_code} - ERROR: {response.text}')
        

    # @api.depends('task_line_ids.available_percent')
    # def _compute_total_available_percentage(self):
    #     for record in self:
    #         if record.available_line_ids:
    #             total = sum(record.available_line_ids.mapped('available_percent'))
    #             record.total_available_percentage = total / len(record.available_line_ids)
    #         else:
    #             record.total_available_percentage = 0

    

    def action_receive_task_digip(self):
        for record in self:
            record.get_digip(record)
            return

    
    def get_digip(self, task):
        for record in self:
            product_list = []
            headers = {}
            params = {
                'PedidoCodigo': task.name,
            }
            url = self.env['ir.config_parameter'].sudo().get_param('digipwms-v2.url')
            headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
            
            response = requests.get(f'{url}/v2/Pedidos', headers=headers, params=params)

            if response.status_code == 200:
                data = response.json()
                if data['estado'] == 'RemitidoExterno':
                    if data['items']:
                        for item in data['items']:
                            product_info = {}
                            product_info['qty_picked'] = item.unidades
                            product_info['product_code'] = item['articulo']['codigo']

                            
                else:
                    raise UserError('El pedido todavía no fué preparado')


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