from datetime import timedelta
from io import BytesIO
import math
from tkinter import Canvas

from odoo import models, fields, api, _
import requests
from odoo.exceptions import UserError, ValidationError
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


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
    invoice_ids = fields.One2many(string="Facturas", comodel_name="account.move", inverse_name="task_id")
    invoice_count = fields.Integer(string="Facturas", compute="_compute_invoice_count")
    invoice_state = fields.Selection(string="Estado de Facturación", selection=[
        ('no', 'No Facturado'),
        ('invoiced', 'Facturado')
    ], default='no')
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

    pending_task_line_ids = fields.One2many(string="Pendiente", comodel_name="wms.task.line", compute="_compute_pending_task_lines")
    declared_value = fields.Float(string="Valor Declarado", default=0)
    next_location_id = fields.Many2one(string="Siguiente Ubicación", comodel_name="wms.stock.location", compute="_compute_next_location")

    ## statistics

    percent_complete = fields.Float(string="Completado %")

    # category_ids = fields.One2many()

    bultos_count = fields.Float(string="Bultos")
    bultos_prepared = fields.Float(string="Bultos Preparados")
    packages_count = fields.Float(string="Paquetes")


    # scheduled_at = fields.Datetime()

    date_start = fields.Datetime(string="Inicio")

    date_done = fields.Datetime(string="Fin")

    preparation_time = fields.Datetime(string="Tiempo de Preparación")
    
    shared_route = fields.Selection([('no', 'No Enviado HDR'), ('si', 'Enviado HDR')], default='no', string='Ruteo HDR', copy=False)
    
    # transporte
    carrier_id = fields.Many2one(string="Transporte", related='partner_id.property_delivery_carrier_id', store=True)

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

    
    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = len(rec.invoice_ids)
    

    def calculate_bultos_demand(self):
        for record in self:
            total_bultos = 0
            for line in record.task_line_ids:
                line_bultos = line.quantity / line.transfer_line_id.uxb
                total_bultos += line_bultos

            record.bultos_count = total_bultos


    @api.depends('task_line_ids.has_pending')
    def _compute_pending_task_lines(self):
        for record in self:            
            record.pending_task_line_ids = self.env['wms.task.line'].search([
                ('task_id', '=', record.id),
                ('has_pending', '=', True)
            ])


    # @api.depends('pending_task_lines')
    # def _compute_next_location(self):
    #     for record in self:
            

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
    

    # OMITIR CODIGO durante el picking

    # def omitir_codigo(self):


    # def lanzar_pedido(self):



















    def action_send_task_to_digip(self):    
        for record in self:
            
            if record.digip_state != 'no':
                continue

            task = {
                "codigo": record.name,
                "clienteUbicacionCodigo": "u"+str(record.partner_address_id.id),
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
                total_bultos = 0

                for line in record.task_line_ids:
                    total_bultos += line.quantity_picked / line.transfer_line_id.uxb
                record.bultos_prepared = total_bultos

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
            task.get_digip_preparations()
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
            task.date_done = fields.Date.context_today(self)
        return True   

    def get_digip_preparations(self):
        for task in self:
            url = self.env['ir.config_parameter'].sudo().get_param('digipwms-v2.url')
            api_key = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')

            headers = {"x-api-key": api_key}
            params = {"PedidoCodigo": task.name}

            response = requests.get(f"{url}/v2/Preparaciones/ContenedoresDetalle", headers=headers, params=params, timeout=30)
            if response.status_code != 200:
                raise UserError(_("Digip devolvió %s: %s") % (response.status_code, response.text))

            data = response.json()

            


            total_packages = sum(
                cont.get("cantidadBulto", 0)
                for cont in data.get("contenedores", [])
            )
            
            task.packages_count = total_packages


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
            'url': f'/newremito/auto/{self.id}',
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
        c = canvas.Canvas(buffer, pagesize=A4)

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
        partner_shipping = task.partner_address_id


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
                uxb = line.transfer_line_id.uxb
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
                    'lote': '123',
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
                'address': partner_shipping.street[:54] or '',
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
            'total_bultos': task.packages_count,
            'total_units': task.bultos_count,
            'total_value': task.declared_value,
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

    # INVOICE

    def action_create_invoice_from_picking(self):
        self.ensure_one()

        sale_id = self.transfer_id.sale_id
        if not sale_id:
            raise UserError("La transferencia no está vinculada a ningún pedido de venta.")

        tipo = self.invoicing_type
        proportion_blanco, proportion_negro = {
            'TIPO 1': (1.0, 0.0),
            'TIPO 2': (0.5, 0.5),
            'TIPO 3': (0.0, 1.0),
            'TIPO 4': (0.25, 0.75),
        }.get(tipo, (1.0, 0.0))

        company_blanca = self.company_id
        company_negra = self.env['res.company'].browse(1)

        invoice_lines_blanco = []
        invoice_lines_negro = []
        sequence = 1

        for line in self.task_line_ids:
            base_vals = line.sale_line_id._prepare_invoice_line(sequence=sequence)

            qty_total = line.quantity_picked
            qty_blanco = math.floor(qty_total * proportion_blanco)
            qty_negro = qty_total - qty_blanco

            if proportion_blanco > 0:
                blanco_vals = base_vals.copy()
                blanco_vals['quantity'] = qty_blanco
                blanco_vals['company_id'] = company_blanca.id
                taxes = line.sale_line_id.tax_id
                blanco_vals['tax_ids'] = [(6, 0, taxes.ids)] if taxes else False
                invoice_lines_blanco.append((0, 0, blanco_vals))

            if proportion_negro > 0:
                negro_vals = base_vals.copy()
                negro_vals['quantity'] = qty_negro
                negro_vals['company_id'] = company_negra.id
                if tipo == 'TIPO 3':
                    negro_vals['price_unit'] *= 1
                else:
                    negro_vals['price_unit'] *= 1.21
                
                negro_vals['tax_ids'] = False
                invoice_lines_negro.append((0, 0, negro_vals))

            sequence += 1

        invoices = self.env['account.move']

        # Crear factura blanca
        if invoice_lines_blanco:            
            vals_blanco = self._prepare_invoice_base_vals(company_blanca)

            vals_blanco['invoice_line_ids'] = invoice_lines_blanco
            vals_blanco['invoice_user_id'] = sale_id.user_id
            vals_blanco['partner_bank_id'] = False            
            vals_blanco['company_id'] = company_blanca.id

            if not vals_blanco.get('journal_id'):
                journal = self.env['account.journal'].search([
                    ('type', '=', 'sale'),
                    ('company_id', '=', company_blanca.id),                    
                    ('code', '=', '00010')
                ], limit=1)
                if not journal:
                    raise UserError(f"No se encontr\u00f3 un diario de ventas para la compa\u00f1\u00eda {self.company_id.name}.")
                vals_blanco['journal_id'] = journal.id

            invoices += self.env['account.move'].with_company(company_blanca).create(vals_blanco)

        # Crear factura negra
        if invoice_lines_negro:
            vals_negro = self._prepare_invoice_base_vals(company_negra)
            vals_negro['invoice_line_ids'] = invoice_lines_negro
            vals_negro['invoice_user_id'] = sale_id.user_id                        
            vals_negro['company_id'] = company_negra

            # Asignar journal correcto
            journal = self.env['account.journal'].search([
                ('type', '=', 'sale'),
                ('company_id', '=', company_negra.id)
            ], limit=1)
            if not journal:
                raise UserError("No se encontró un diario de ventas para Producción B.")
            vals_negro['journal_id'] = journal.id
            vals_negro['partner_bank_id'] = False

            invoices += self.env['account.move'].with_company(company_negra).create(vals_negro)

        # Relacionar con la transferencia
        invoices.write({
            'invoice_origin': self.origin or self.name,
        })

        self.invoice_ids = [(6, 0, invoices.ids)]
        self.invoice_state = 'invoiced'

        for line in self.task_line_ids.filtered(lambda m: m.sale_line_id):
            line.sale_line_id.qty_invoiced += line.quantity_picked
            line.transfer_line_id.qty_invoiced += line.quantity_picked
            
        #sacar todas las facturas
        #Enviar el invoice_id al tms_stock_picking
        # tms_stock = self.env['tms.stock.picking'].search([('codigo_wms', '=', self.codigo_wms)], limit=1)
        # if tms_stock:
        #     invoices = self.env['account.move'].browse(self.invoice_ids.ids)
        #     rubros_ids = []
        #     amount_total = 0
        #     amount_nc_total = 0
        #     for invoice in invoices:
        #         #separar facturas de cliente y notas de credito
        #         if invoice.line_type == 'out_refund' and invoice.state != 'cancel':
        #             amount_nc_total += invoice.amount_total
        #         elif invoice.line_type == 'out_invoice' and invoice.state != 'cancel':
        #             amount_total += invoice.amount_total
        #         items = invoice.invoice_line_ids.mapped('product_id.categ_id.parent_id')
        #         items = items.filtered(lambda c: c and c.id).ids
        #         rubros_ids = list(set(rubros_ids + items))
            
        #     #quitar los rubros duplicados
        #     rube_ids_final = list(set(rubros_ids))
        #     tms_stock.write({'account_line_ids': self.invoice_ids.ids, 'amount_totals': amount_total, 'amount_nc_totals': amount_nc_total, 'items_ids': rube_ids_final})

        if len(self.invoice_ids) == 1:
            return {
                'name': "Factura generada",
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'form',
                'res_id': self.invoice_ids[0].id,
            }
        else:
            return {
                'name': "Facturas generadas",
                'type': 'ir.actions.act_window',
                'res_model': 'account.move',
                'view_mode': 'tree,form',
                'domain': [('id', 'in', self.invoice_ids.ids)],
            }
    
    def action_create_tms_roadmap(self):
        for record in self:
            tms_roadmap_id = record.env['tms.roadmap'].search([('wms_task_id', '=', record.id)], limit=1)
            if not tms_roadmap_id:
                tms_roadmap_id = record.env['tms.roadmap'].create({
                    'wms_task_id': record.id,
                    'origin': record.origin,
                    'partner_id': record.partner_id.id,
                    'date': fields.Datetime.context_today(self),
                    'transport_id': record.carrier_id.id,
                    'direction': record.carrier_id.address,
                    'in_ruta': 1,
                    'bulto_count': record.bultos_prepared if record.bultos_prepared > 0 else record.bultos_count,
                    'bulto_count_verified': record.bultos_prepared if record.bultos_prepared > 0 else record.bultos_count,
                })
                
                return {
                    'name': "Hoja de Ruta",
                    'type': 'ir.actions.act_window',
                    'res_model': 'tms.roadmap',
                    'view_mode': 'form',
                    'res_id': tms_roadmap_id.id,
                }
            else:
                return {
                    'name': "Hoja de Ruta",
                    'type': 'ir.actions.act_window',
                    'res_model': 'tms.roadmap',
                    'view_mode': 'form',
                    'res_id': tms_roadmap_id.id,
                }

    def _prepare_invoice_base_vals(self, company):
        invoice_date_due = fields.Date.context_today(self)

        sale_id = self.transfer_id.sale_id

        if sale_id.payment_term_id:
            extra_days = max(sale_id.payment_term_id.line_ids.mapped('days') or [0])
            invoice_date_due = self.set_due_date_plus_x(extra_days)
        
        
        return {
            'move_type': 'out_invoice',
            'partner_id': sale_id.partner_invoice_id,
            'partner_shipping_id': sale_id.partner_shipping_id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': invoice_date_due,
            'company_id': sale_id.company_id.id,
            'currency_id': sale_id.company_id.currency_id.id,
            'invoice_origin': self.origin or self.name,
            'payment_reference': self.name,
            'fiscal_position_id': sale_id.partner_invoice_id.property_account_position_id.id,
            'invoice_payment_term_id': sale_id.payment_term_id,
            'wms_code': self.name,
            'pricelist_id': sale_id.pricelist_id.id,
            'special_price': sale_id.special_price,
        }
    
    def set_due_date_plus_x(self, x):
        today = fields.Date.context_today(self)
        new_date = today + timedelta(days=x)
        return new_date


    ### TITO CODIGO COMPARTIDO ###
    def _fmt_dt_local(self, dt):
        """datetime -> string en zona del usuario."""
        if not dt:
            return ""
        dt_local = fields.Datetime.context_timestamp(self, dt)  # tz del usuario
        return dt_local.strftime('%d/%m/%Y')

    def action_forzar_envio_compartido(self):
        for record in self:
            record.action_enviar_compartido(envio_forzar=True)
    
    def action_enviar_compartido(self, envio_forzar=False):
        for record in self:
            if record.digip_state != 'sent' and not envio_forzar:
                raise ValidationError(_("El remito %s, debe estar en preparación para enviarlo al compartido.") % record.name)
            if record.shared_route == 'si' and not envio_forzar:
                raise ValidationError(_("El remito con la Tarea %s, ya fue enviado al compartido anteriormente.") % record.name)
            direccion_entrega = ""
            cliente = ""
            if record.carrier_id:
                if record.carrier_id.name == 'Reparto Propio':
                    direccion_entrega = f"{record.partner_id.street or '-'}, {record.partner_id.zip or '-'}, {record.partner_id.city or '-' }"
                else:
                    direccion_entrega = record.carrier_id.address
            if record.partner_id:
                if record.partner_id.parent_id:
                    cliente = f"{record.partner_id.parent_id.name}, {record.partner_id.name}"
                else:
                    cliente = record.partner_id.name
            try:
                values = [
                    "",                                          # A
                    record._fmt_dt_local(record.transfer_id.create_date),   # B
                    record.name or "",                     # C
                    record.transfer_id.origin or "",                         # D
                    record.transfer_id.name or "",                           # E
                    cliente,                                    # F
                    (round(record.bultos_count, 2) or ""),     # G
                    len(record.task_line_ids) or 0,   # H
                    "",                                          # I
                    "",                                          # J
                    "", "", "", "",                              # K L M N
                    "", "",                                      # O P
                    record.partner_id.industry_id.name or "",    # Q
                    record.carrier_id.name or "",                # R
                    direccion_entrega,                           # S
                    record.partner_id.street or "",              # T
                    record.partner_id.zip or "",                 # U
                    record.partner_id.city or "",                # V
                    "0",                                         # W
                    record.transfer_id.sale_id.company_id.name if record.transfer_id.sale_id and record.transfer_id.sale_id.company_id else "",                                          # X
                ]
                enviado = record.env["google.sheets.client"].append_row(values)
                if enviado == 200 and record.shared_route == 'no':
                    record._crear_tms_stock_picking()
                    record.write({'shared_route': 'si'})
            except Exception as e:
                raise ValidationError(_("Fallo enviando a Google Sheets para picking %s: %s") % (record.name, e))

    def _crear_tms_stock_picking(self):
        tms = self.env['tms.stock.picking'].search([('wms_task_id', '=', self.id)], limit=1)
        if not tms:
            direccion_entrega = ""
            if self.carrier_id:
                if self.carrier_id.name == 'Reparto Propio':
                    direccion_entrega = f"{self.partner_id.street or '-'}, {self.partner_id.zip or '-'}, {self.partner_id.city or '-' }"
                else:
                    direccion_entrega = self.carrier_id.address
            vals = {
                'name': self.transfer_id.name,
                'wms_task_id': self.id,
                'picking_ids': [(4, self.id)],
                'fecha_entrega': False,
                'fecha_envio_wms': self.transfer_id.create_date,
                'codigo_wms': self.name,
                'doc_origen': self.origin,
                'partner_id': self.partner_id.id,
                'cantidad_bultos': self.bultos_count,
                'cantidad_lineas': len(self.task_line_ids) or 0,
                'carrier_id': self.carrier_id.id,
                'observaciones': '',
                'industry_id': self.partner_id.industry_id.id,
                'ubicacion': '',
                'estado_digip': self.digip_state,
                'estado_despacho': 'in_preparation',
                'sale_id': self.transfer_id.sale_id.id if self.transfer_id.sale_id else False,
                'fecha_despacho': False,
                'observacion_despacho': False,
                'contacto_calle': self.partner_id.street or False,
                'direccion_entrega': direccion_entrega,
                'contacto_cp': self.partner_id.zip or False,
                'contacto_ciudad': self.partner_id.city or False,
                'company_id': self.transfer_id.sale_id.company_id.id if self.transfer_id.sale_id and self.transfer_id.sale_id.company_id else False,
                'user_id': self.env.user.id,
            }
            tms = self.env['tms.stock.picking'].create(vals)


class WMSTaskLine(models.Model):
    _name = 'wms.task.line'

    name = fields.Char()
    task_id = fields.Many2one(string="Tarea", comodel_name="wms.task")
    transfer_line_id = fields.Many2one(string="Línea de Transferencia", comodel_name="wms.transfer.line")
    sale_line_id = fields.Many2one(string="Línea de Pedido de Venta", comodel_name="sale.order.line")
    product_id = fields.Many2one(string="Producto", comodel_name="product.product")
    quantity = fields.Integer(string="Demanda")
    quantity_picked = fields.Integer(string="Cantidad pickeada")
    quantity_controlled = fields.Integer(string="Cantidad Controlada")
    lot = fields.Char(string="Lote")

    is_broken = fields.Boolean(string="¿Está roto?")
    has_pending = fields.Boolean(string="Tiene pendiente", compute="_compute_has_pending", store=True, default=False)
    location_id = fields.Many2one(string="Ubicación de Picking")


    @api.depends('quantity_picked')
    def _compute_has_pending(self):
        for record in self:
            if record.quantity_picked < record.quantity:
                record.has_pending = True
            else:
                record.has_pending = False