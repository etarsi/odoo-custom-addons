from io import BytesIO
import math
from tkinter import Canvas

from odoo import models, fields, api, _
import requests
from odoo.exceptions import UserError
from reportlab.lib.pagesizes import A4


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
    invoicing_type = fields.Char(string="Tipo de Facturación")
    priority = fields.Integer(string="Prioridad")
    assigned_user_id = fields.Many2one(string="Asignado a", comodel_name="res.users")
    task_line_ids = fields.One2many(string="Líneas de Tarea", comodel_name="wms.task.line", inverse_name="task_id")
    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")
    partner_id = fields.Many2one(string="Contacto", comodel_name="res.partner")
    partner_address_id = fields.Many2one(string="Dirección de Entrega", comodel_name="res.partner")
    origin = fields.Char(string="Documento")
    company_id = fields.Many2one(string="Compañía", comodel_name="res.company")
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
    date_start = fields.Datetime(string="Inicio")
    date_done = fields.Datetime(string="Fin")
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
            
            if record.digip_state != 'no':
                continue

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
        for task in self:
            if task.digip_state != 'sent':
                continue
            task.get_digip()
        return True
    

    def get_digip(self):
        for task in self:
            url = self.env['ir.config_parameter'].sudo().get_param('digipwms-v2.url')
            api_key = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')

            headers = {"x-api-key": api_key}
            params = {"PedidoCodigo": task.name}

            response = requests.get(f"{url}/v2/Pedidos", headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                raise UserError(_("Digip devolvió %s: %s") % (response.status_code, response.text))

            data = response.json()

            if not data:
                raise UserError(_("Digip no devolvió resultados para PedidoCodigo=%s") % task.name)

            pedido = data[0]
            if pedido.get("estado") not in ("RemitidoExterno", "Completo"):
                raise UserError(_("El pedido todavía no fue preparado (estado: %s).") % (pedido.get("estado"),))

            items = pedido.get("items") or []
            if not items:
                raise UserError(_("El pedido en Digip no tiene items."))

            picked_by_code = {}
            for item in items:
                code = ((item.get("articulo") or {}).get("codigo") or "").strip()
                qty_picked = int(item.get("unidadesSatisfecha") or 0)
                if not code:
                    continue
                picked_by_code[code] = picked_by_code.get(code, 0) + qty_picked

            line_by_code = {}
            for line in task.task_line_ids:
                code = (line.product_id.default_code or "").strip()
                if code:
                    line_by_code[code] = line

            updated = 0
            for code, qty_picked in picked_by_code.items():
                line = line_by_code.get(code)
                if line:
                    line.write({"quantity_picked": qty_picked})
                    line.write({"quantity_controlled": qty_picked})
                    updated += 1

            Product = self.env["product.product"]
            TaskLine = self.env["wms.task.line"]
            created = 0
            for code, qty_picked in picked_by_code.items():
                if code in line_by_code:
                    continue
                product = Product.search([("default_code", "=", code)], limit=1)
                if product:
                    TaskLine.create({
                        "task_id": task.id,
                        "product_id": product.id,
                        "quantity": 0,
                        "quantity_picked": qty_picked,
                        "quantity_controlled": qty_picked,
                    })
                    created += 1
            task.digip_state = "received"
        return True


    def send_and_receive_digip(self):
        for record in self:
            if record.digip_state == 'no':
                record.action_send_task_to_digip()
            elif record.digip_state == 'sent':
                record.action_receive_task_digip()


    ### REMITO 
    def action_print_remito(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_url',
            'url': f'/nremito/auto/{self.id}',
            'target': 'new',
        }

    def _build_remito_pdf(self, task, proportion, company_id, type):
        remito = self._prepare_remito_data(task, proportion, company_id, type)
        rcoords = self.get_new_remito_coords()
        config_param = self.env['ir.config_parameter']
        left = int(config_param.sudo().get_param('remito_margen_left'))
        right = int(config_param.sudo().get_param('remito_margen_right'))
        top = int(config_param.sudo().get_param('remito_margen_top'))
        bottom = int(config_param.sudo().get_param('remito_margen_bottom'))

        buffer = BytesIO()
        c = Canvas.Canvas(buffer, pagesize=A4)

        # ----------- FUNCIONES PARA HEADER Y TABLA -----------
        def draw_header():
            c.setLineWidth(1)
            container_x = int(config_param.sudo().get_param('container_x'))
            container_y = int(config_param.sudo().get_param('container_y'))
            container_width = right - left
            container_height = int(config_param.sudo().get_param('container_h'))
            c.roundRect(container_x, container_y, container_width, container_height, radius=10)

            c.setFont("Helvetica-Bold", 13)
            c.drawString(rcoords['fecha_x'], rcoords['fecha_y'], "FECHA: " + (remito.get('date', "")))
            c.setFont("Helvetica", 10)
            c.drawString(rcoords['cliente_x'], rcoords['cliente_y'], f"Cliente: {remito['client']['name']}")
            c.drawString(rcoords['direccion_x'], rcoords['direccion_y'], f"Dirección: {remito['client']['address']}")
            c.drawString(rcoords['localidad_x'], rcoords['localidad_y'], f"Localidad: {remito['client']['location']}")
            c.drawString(rcoords['iva_x'], rcoords['iva_y'], f"IVA: {remito['client']['iva']}")
            c.drawString(rcoords['cuit_x'], rcoords['cuit_y'], f"CUIT: {remito['client']['cuit']}")
            c.drawString(rcoords['transporte_x'], rcoords['transporte_y'], f"Transporte: {remito['destination']['name']}")
            c.drawString(rcoords['transporte2_x'], rcoords['transporte2_y'], f"{remito['destination']['address']}")
            c.drawString(rcoords['pedido_x'], rcoords['pedido_y'], f"Pedido: {remito['origin']}")
            c.drawString(rcoords['transferencia_x'], rcoords['transferencia_y'], f"Tarea: {remito['task_name']}")

        def draw_table_headers():
            tabla_top = top
            tabla_left = left
            tabla_right = right
            tabla_bottom = bottom
            col_bultos = left + 10
            col_codigo = left + 55
            col_producto = left + 100
            col_lote = left + 380
            col_unidades = right - 50

            c.setLineWidth(1)
            c.roundRect(tabla_left, tabla_bottom, tabla_right - tabla_left, tabla_top - tabla_bottom, radius=10)
            c.line(col_codigo-10, tabla_top, col_codigo-10, tabla_bottom)
            c.line(col_producto-9, tabla_top, col_producto-10, tabla_bottom)
            c.line(col_lote, tabla_top, col_lote, tabla_bottom)        
            c.line(col_unidades, tabla_top, col_unidades, tabla_bottom)

            c.setFont("Helvetica-Bold", 9)
            c.drawString(col_bultos -1, tabla_top - 15, "Bultos")
            c.drawString(col_codigo-1, tabla_top - 15, "Código")
            c.drawString(col_producto, tabla_top - 15, "Descripción")
            c.drawString(col_lote +10, tabla_top - 15, "Despacho")
            c.drawString(col_unidades+5, tabla_top - 15, "Unidades")
            c.line(tabla_left, tabla_top - 20, tabla_right, tabla_top - 20)
            return tabla_top, tabla_left, tabla_right, tabla_bottom, col_bultos, col_codigo, col_producto, col_lote, col_unidades

        def draw_footer():
            c.setFont("Helvetica-Bold", 10)
            c.drawString(left, bottom - 20, f"Cantidad de Bultos: {remito.get('total_bultos', 0):.2f}")
            c.drawString(left + 200, bottom - 20, f"Cantidad UXB: {remito.get('total_units', 0):.2f}")
            if remito.get('total_value'):
                c.drawString(right - 120, bottom - 20, f"Total: $ {remito['total_value']:,.2f}")

        # ----------- MAIN LOOP: MULTI-PÁGINA -----------
        max_rows_per_page = 32
        row_height = 13

        line_lines = remito['line_lines']
        num_lines = len(line_lines)
        line_idx = 0

        while line_idx < num_lines:
            draw_header()
            tabla_top, tabla_left, tabla_right, tabla_bottom, col_bultos, col_codigo, col_producto, col_lote, col_unidades = draw_table_headers()
            y = tabla_top - 35

            for row in range(max_rows_per_page):
                if line_idx >= num_lines or y < tabla_bottom + row_height:
                    break
                linea = line_lines[line_idx]
                c.setFont("Helvetica", 8)
                c.drawString(col_bultos+1, y, f"{linea['bultos']:.2f}")
                c.drawString(col_codigo, y, linea['code'])
                c.drawString(col_producto, y, linea['description'])
                c.drawString(col_lote +10, y, linea['lote'])
                c.drawRightString(col_unidades + 35, y, f"{int(linea['unidades'])}")
                y -= row_height
                line_idx += 1

            # FOOTER (al pie de cada página)
            draw_footer()
            if line_idx < num_lines:
                c.showPage()

        c.save()
        pdf = buffer.getvalue()
        buffer.close()
        return pdf


    def _prepare_remito_data(self, task, proportion, company_id, type):
        partner = task.partner_id

        lines = []
        total_bultos = 0
        total_unidades = 0
        date = task.date_done
        date = date.strftime('%d-%m-%Y')

        if partner.type == 'contact':            
            partner_name = f"{partner.name}"
        else:            
            partner_name = f"{partner.parent_id.name}"
        

        partner_name = partner_name[:45]

        if type == 'b':
            partner_name = f"{partner_name}*"
            
        

        for line in task.task_line_ids:
            qty = line.quantity_picked * proportion

            # redeondeo unidades con decimal según blanco/negro el remito
            if qty % 1 != 0:
                if type == 'a':
                    qty = math.floor(qty) # redondeo para abajo
                if type == 'b':
                    qty = math.ceil(qty) # redondeo para arriba


            if qty > 0:
                uxb = line.uxb
                bultos = qty / uxb if uxb else 1
                lote = line.lot
                product_code = line.product_id.default_code
                product_description = f"{line.product_id.name}"
                product_description = product_description[:55]
                product_name = f"[{line.product_id.default_code}] {line.product_id.name}"
                product_name = product_name[:60]

                
                lines.append({
                    'bultos': bultos,
                    'code': product_code,
                    'description': product_description,
                    'nombre': product_name,
                    'lote': lote,
                    'unidades': qty,
                })

                total_bultos += bultos
                total_unidades += qty
        
        # total_value = task.declared_value
        # if total_value == 0:
        #     total_value = False
        
        client_location = f"{partner.city}, {partner.state_id.name}"

        remito = {
            'date': date,
            'client': {
                'name': partner_name,
                'address': partner.street[:54] or '',
                'location': client_location[:54] or '',
                'cuit': partner.vat,
                'iva': partner.l10n_ar_afip_responsibility_type_id.name if partner.l10n_ar_afip_responsibility_type_id else '',
            },
            'origin': task.origin or '',
            'task_name': task.name[:20] or '',
            'destination': {
                'name': f"{partner.property_delivery_carrier_id.name or ''}",
                'address': f"{partner.property_delivery_carrier_id.address or ''}",
            },
            'line_lines': lines,
            'total_bultos': 0,
            'total_units': 0,
            'total_value': 0,
            'company_name': company_id.name,
        }

        return remito


    def get_new_remito_coords(self):
        remito_coords = self.env['remito.coords'].search([], limit=1)

        if remito_coords:

            return {            
                'fecha_x': remito_coords.fecha_x,
                'fecha_y': remito_coords.fecha_y,
                'cliente_x': remito_coords.cliente_x,
                'cliente_y': remito_coords.cliente_y,                
                'direccion_x': remito_coords.direccion_x,
                'direccion_y': remito_coords.direccion_y,                
                'localidad_x': remito_coords.localidad_x,
                'localidad_y': remito_coords.localidad_y,                
                'iva_x': remito_coords.iva_x,
                'iva_y': remito_coords.iva_y,                
                'cuit_x': remito_coords.cuit_x,
                'cuit_y': remito_coords.cuit_y,                
                'tel_x': remito_coords.tel_x,
                'tel_y': remito_coords.tel_y,                
                'transporte_x': remito_coords.transporte_x,
                'transporte_y': remito_coords.transporte_y,            
                'transporte2_x': remito_coords.transporte2_x,
                'transporte2_y': remito_coords.transporte2_y,               
                'pedido_x': remito_coords.pedido_x,
                'pedido_y': remito_coords.pedido_y,
                'transferencia_x': remito_coords.transferencia_x,
                'transferencia_y': remito_coords.transferencia_y,
                'wms_x': remito_coords.wms_x,
                'wms_y': remito_coords.wms_y,
                'bultos_x': remito_coords.bultos_x,
                'bultos_y': remito_coords.bultos_y,
                'cod_x': remito_coords.cod_x,
                'cod_y': remito_coords.cod_y,
                'descripcion_x': remito_coords.descripcion_x,
                'descripcion_y': remito_coords.descripcion_y,
                'despacho_x': remito_coords.despacho_x,
                'despacho_y': remito_coords.despacho_y,
                'unidades_x': remito_coords.unidades_x,
                'unidades_y': remito_coords.unidades_y,
                'cantidad_bultos_x': remito_coords.cantidad_bultos_x,
                'cantidad_bultos_y': remito_coords.cantidad_bultos_y,
                'cantidad_paquetes_x': remito_coords.cantidad_paquetes_x,
                'cantidad_paquetes_y': remito_coords.cantidad_paquetes_y,
                'valor_declarado_x': remito_coords.valor_declarado_x,
                'valor_declarado_y': remito_coords.valor_declarado_y,
            }

class WMSTaskLine(models.Model):
    _name = 'wms.task.line'

    name = fields.Char()
    task_id = fields.Many2one(string="Tarea", comodel_name="wms.task")
    transfer_line_id = fields.Many2one(string="Línea de Transferencia", comodel_name="wms.transfer.line")
    product_id = fields.Many2one(string="Producto", comodel_name="product.product")
    quantity = fields.Integer(string="Demanda")
    quantity_picked = fields.Integer(string="Cantidad pickeada")
    quantity_controlled = fields.Integer(string="Cantidad Controlada")
    lot = fields.Char(string="Lote")

    is_broken = fields.Boolean(string="¿Está roto?")