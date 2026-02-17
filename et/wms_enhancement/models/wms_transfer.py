from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class WMSTransfer(models.Model):
    _name = 'wms.transfer'

    name = fields.Char()
    partner_id = fields.Many2one(string="Cliente", comodel_name="res.partner")
    partner_address_id = fields.Many2one(string="Dirección de Entrega", comodel_name="res.partner")
    operation_type = fields.Selection(string="Tipo de Operación", selection=[
        ('incoming', 'Ingreso'),
        ('return', 'Devolución'),
        ('internal', 'Interno'),
        ('outgoing', 'Entrega'),
    ])
    state = fields.Selection(string="Estado", selection=[
        ('no', 'No aplica'),
        ('pending', 'Pendiente'),
        ('process', 'En Proceso'),
        ('finished', 'Finalizada')
    ], default='no')
    sale_type = fields.Char(string="TIPO")
    preselection_id = fields.Many2one(string="Preselección", comodel_name="wms.preselection")
    sale_id = fields.Many2one(string="Pedido de Venta", comodel_name="sale.order")
    purchase_id = fields.Many2one(string="Pedido de Compra", comodel_name="purchase.order")
    invoice_ids = fields.One2many(string="Facturas", comodel_name="account.move", inverse_name="transfer_id")
    line_ids = fields.One2many(string="Líneas de  Transferencia", comodel_name="wms.transfer.line", inverse_name="transfer_id")
    available_line_ids = fields.One2many(string="Líneas de  Transferencia", comodel_name="wms.transfer.line", compute="_compute_available_line_ids")
    task_ids = fields.One2many(string="Tareas", comodel_name="wms.task", inverse_name="transfer_id")
    task_count = fields.Integer(string="Tareas", compute="_compute_task_count")
    lines_count = fields.Integer(string="Cantidad de Líneas", compute="_compute_lines_count")
    origin = fields.Char(string="Documento")
    

    partner_tag = fields.Many2many()
    products_categ = fields.Many2many()

    total_bultos = fields.Float(string="Bultos")
    total_bultos_prepared = fields.Float(string="Bultos Preparados")
    total_available_percentage = fields.Float(string="Porcentaje Disponible")


    @api.model
    def create(self, vals):
        if vals.get('name', 'New') in (False, 'New', '/'):
            vals['name'] = self.env['ir.sequence'].next_by_code('wms.transfer') or 'New'

        sale_id = vals.get('sale_id')
        if sale_id and 'origin' in self._fields and not vals.get('origin'):
            sale = self.env['sale.order'].browse(sale_id)
            if sale.exists():
                vals['origin'] = sale.name

        purchase_id = vals.get('purchase_id')
        if purchase_id and 'origin' in self._fields and not vals.get('origin'):
            purchase = self.env['purchase.order'].browse(purchase_id)
            if purchase.exists():
                vals['origin'] = purchase.name


        preselection_id = vals.get('preselection_id')
        if preselection_id and 'origin' in self._fields and not vals.get('origin'):
            preselection = self.env['wms.preselection'].browse(preselection_id)
            if preselection.exists():
                vals['origin'] = preselection.name


        return super().create(vals)


    @api.depends('task_ids')
    def _compute_task_count(self):
        for rec in self:
            rec.task_count = len(rec.task_ids)


    @api.depends('available_line_ids')
    def _compute_lines_count(self):
        for rec in self:
            rec.lines_count = len(rec.available_line_ids)


    @api.depends('line_ids.is_available')
    def _compute_available_line_ids(self):
        for transfer in self:
            transfer.available_line_ids = self.env['wms.transfer.line'].search([
                ('transfer_id', '=', transfer.id),
                ('is_available', '=', True)
            ])


    @api.onchange('line_ids.bultos')
    def _onchange_bultos(self):
        for record in self:
            if record.line_ids:
                record.total_bultos = 0 # ESTABA


    def update_availability(self):
        for record in self:
            if record.available_line_ids:
                record.available_line_ids.update_availability()                   



    # ACTIONS

    
    def action_split_into_tasks(self, max_lines=30, max_bultos=30):
        """
        Crea tareas consumiendo qty_pending de las líneas disponibles (available_percent == 100).
        Soporta partir una misma wms.transfer.line entre múltiples tareas.
        """
        self.ensure_one()

        lines = self.line_ids.filtered(lambda l:
            float_compare(l.available_percent or 0.0, 100.0, precision_digits=6) == 0
            and (l.qty_pending or 0) > 0
        )

        if not lines:
            raise UserError(_("No hay disponibilidad de stock físico para generar tareas."))

        created_tasks = self.env['wms.task']

        # Bucket (lo que va a ir a UNA tarea)
        bucket = []  # lista de dicts: {'line': wtl, 'qty': unidades, 'bultos': bultos}
        bucket_bultos = 0.0
        bucket_distinct_lines = set()  # ids de wms.transfer.line usados en esta tarea

        def close_bucket():
            nonlocal bucket, bucket_bultos, bucket_distinct_lines, created_tasks
            if not bucket:
                return
            task = self._wms_create_task_from_bucket(bucket)
            created_tasks |= task
            bucket = []
            bucket_bultos = 0.0
            bucket_distinct_lines = set()

        for wtl in lines:
            # Mientras esta línea tenga pendiente, vamos consumiendo en tareas sucesivas
            while (wtl.qty_pending or 0) > 0:
                if not wtl.uxb or wtl.uxb <= 0:
                    raise UserError(_(
                        "La línea %s (%s) no tiene UxB válido (uxb=%s)."
                    ) % (wtl.id, wtl.product_id.display_name, wtl.uxb))

                # Si el bucket ya alcanzó el máximo de líneas distintas, cerramos tarea
                if len(bucket_distinct_lines) >= max_lines and (wtl.id not in bucket_distinct_lines):
                    close_bucket()

                # Bultos disponibles en el bucket actual
                remaining_bucket_bultos = max_bultos - bucket_bultos
                if float_compare(remaining_bucket_bultos, 0.0, precision_digits=6) <= 0:
                    close_bucket()
                    remaining_bucket_bultos = max_bultos

                # Bultos pendientes de la línea (derivado de qty_pending / uxb)
                wtl_pending_bultos = (wtl.qty_pending / float(wtl.uxb))

                # Cuántos bultos tomar de esta línea para esta tarea
                take_bultos = min(wtl_pending_bultos, remaining_bucket_bultos)

                # Convertimos a unidades enteras (bultos * uxb)
                # Importante: como qty_pending es int, y uxb es int, normalmente esto da exacto.
                take_units = take_bultos * wtl.uxb

                # Seguridad: no tomar más que lo pendiente
                take_units = min(take_units, int(wtl.qty_pending))

                if take_units <= 0:
                        # No entra nada en este bucket -> cerrar y seguir
                        close_bucket()
                        continue

                # Agregar al bucket
                bucket.append({
                    'line': wtl,
                    'qty': take_units,
                    'bultos': take_bultos,
                })
                bucket_bultos += take_bultos
                bucket_distinct_lines.add(wtl.id)

                # Consumir del pendiente (esto es lo que evita duplicar)
                wtl.qty_pending -= take_units

                # Si llegamos al límite de bultos o líneas, cerramos tarea
                reached_bultos = float_compare(bucket_bultos, max_bultos, precision_digits=6) >= 0
                reached_lines = len(bucket_distinct_lines) >= max_lines
                if reached_bultos or reached_lines:
                    close_bucket()

        close_bucket()

        self.update_availability()

        return {
            'type': 'ir.actions.act_window',
            'name': _('Tareas WMS'),
            'res_model': 'wms.task',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', created_tasks.ids)],
            'target': 'current',
        }

    def _wms_create_task_from_bucket(self, bucket):
        """
        bucket: lista de dicts {'line': wtl, 'qty': unidades, 'bultos': bultos}
        Crea wms.task + wms.task.line.
        Ajustá los campos a tu modelo real.
        """
        self.ensure_one()

        task = self.env['wms.task'].create({
            'transfer_id': self.id,            
            'origin': self.origin,
            'type': 'preparation',
            'state_preparation': 'pending',
            'partner_id': self.partner_id.id,
        })

        # Si en una misma tarea pudiste agregar la misma transfer.line en 2 "chunks",
        # conviene consolidar por wtl.id para crear 1 sola task.line.
        grouped = {}
        for chunk in bucket:
            wtl = chunk['line']
            grouped.setdefault(wtl.id, {'line': wtl, 'qty': 0})
            grouped[wtl.id]['qty'] += int(chunk['qty'])

        vals_list = []
        for data in grouped.values():
            wtl = data['line']
            qty = data['qty']
            vals_list.append({
                'task_id': task.id,
                'transfer_line_id': wtl.id,
                'product_id': wtl.product_id.id,
                'quantity': qty,
            })

        self.env['wms.task.line'].create(vals_list)
        return task
    

    def action_create_task(self):
        return

    def action_create_tasks_auto(self):

        return
    





    def action_close_transfer(self):
        return
    

    def action_open_purchase(self):
        self.ensure_one()
        if not self.purchase_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pedido de Compra'),
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': self.purchase_id.id,
            'target': 'current',
        }

    def action_open_preselection(self):
        self.ensure_one()
        if not self.preselection_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pedido de Preselección'),
            'res_model': 'wms.preselection',
            'view_mode': 'form',
            'res_id': self.preselection_id.id,
            'target': 'current',
        }
    
    def action_open_sale(self):
        self.ensure_one()
        if not self.sale_id:
            return False

        return {
            'type': 'ir.actions.act_window',
            'name': _('Pedido de Venta'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'res_id': self.sale_id.id,
            'target': 'current',
        }




class WMSTransferLine(models.Model):
    _name = 'wms.transfer.line'

    name = fields.Char()
    transfer_id = fields.Many2one(string="Transferencia", comodel_name="wms.transfer")
    state = fields.Selection(string="Estado", selection=[
        ('pending', 'Pendiente'),
        ('preparation', 'En Preparación'),
        ('done', 'Hecho'),
    ])
    invoice_state = fields.Selection(string="Estado de Facturación", selection=[
        ('no', 'No Facturado'),
        ('partial', 'Parcial'),
        ('total', 'Facturado'),
    ])
    product_id = fields.Many2one(string="Producto", comodel_name="product.product")
    sale_line_id = fields.Many2one(string="Línea del Pedido de Venta", comodel_name="sale.order.line")
    lot_name = fields.Char(string="Lote")
    uxb = fields.Integer(string="UxB")
    availability = fields.Char(string="Disponibilidad")
    qty_demand = fields.Integer(string="Demanda Inicial")
    qty_pending = fields.Integer(string="Pendiente")
    qty_done = fields.Integer(string="Preparado")
    qty_invoiced = fields.Integer(string="Facturado")
    available_percent = fields.Float(string="Disponible Preparación")
    is_available = fields.Boolean(string="Disponible Comercial", compute="_compute_is_available")

    bultos = fields.Float(string="Bultos", compute="_compute_bultos", store=True)
    bultos_available = fields.Float(string="Bultos Disponible")


    @api.model
    def create(self, vals):
        
        product_id = vals.get('product_id')

        stock_erp = self.env['stock.erp'].search([
            ('product_id', '=', product_id)
        ], limit=1)

        if stock_erp:
            fisico_unidades = stock_erp.fisico_unidades
        else:
            raise UserWarning("No se encontró stock para el producto [{stock_erp.product_code}] {stock_erp.product_name}")
        
        demand = vals.get('qty_demand')
        uxb = stock_erp.uxb

        if demand > 0:
            ratio = fisico_unidades / demand
            available_percent = min(ratio * 100, 100)
        else:
            available_percent = 0

        vals['qty_pending'] = demand
        vals['available_percent'] = available_percent
        vals['bultos_available'] = fisico_unidades / uxb


        return super().create(vals)


    @api.depends('qty_demand')
    def _compute_is_available(self):
        for record in self:
            if record.qty_demand == 0:
                record.is_available = False
            else:
                record.is_available = True


    @api.depends('qty_demand', 'uxb', 'product_id')
    def _compute_bultos(self):
        for record in self:
            if record.qty_demand > 0 and record.uxb > 0 and record.product_id:
                record.bultos = record.qty_demand / record.uxb
            else:
                record.bultos = 0


    def update_availability(self):
        for record in self:
            stock_erp = self.env['stock.erp'].search([
            ('product_id', '=', record.product_id.id)
        ], limit=1)

        if stock_erp:
            fisico_unidades = stock_erp.fisico_unidades
        else:
            raise UserWarning("No se encontró stock para el producto [{stock_erp.product_code}] {stock_erp.product_name}")
        
        pending = record.qty_pending
        uxb = record.uxb
    
        if pending > 0:
            ratio = fisico_unidades / pending
            available_percent = min(ratio * 100, 100)
        else:
            available_percent = 0

        record.available_percent = available_percent
        record.bultos_available = fisico_unidades / uxb