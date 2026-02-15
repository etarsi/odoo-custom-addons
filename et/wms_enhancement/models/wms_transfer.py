from odoo import models, fields, api, _


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

    def action_create_task_digip(self):
        for record in self:
            record.update_availability()

            ### TASK CREATION

            while True:
                selected_lines = self.env['wms.transfer.lines']
                line_count = 0
                bulto_count = 0
                lines_to_split = record.available_line_ids.filtered(lambda m: m.available_percent == 100)

                for line in lines_to_split:
                    if line_count >= 30 or bulto_count >= 30:
                        break

                    line_bultos = line.qty_pending / line.uxb

                    if bulto_count + line_bultos > 30:
                        continue
                    line_count += 1
                    bulto_count += line.bultos
                    selected_lines |= line

                if not selected_lines:
                    break
                if len(selected_lines) == len(record.available_line_ids):
                    break

                new_task = record._split_off_moves(selected_lines)
                all_new_task |= new_task

            record.update_availability()
            all_new_task |= record
        

        all_new_task.update_availability()
        if all_new_task:
            return {
                'name': 'Facturas Divididas',
                'type': 'ir.actions.act_window',
                'view_mode': 'tree,form',
                'res_model': 'stock.picking',
                'domain': [('id', 'in', all_new_task.ids)],
            }









            task_vals = {
                'transfer_id': record.id,
                'partner_id':record.partner_id.id,                
                'state': 'pending',
            }

            task_id = self.env['wms.task'].create(task_vals)

            transfer_lines_list = []
            for line in record.order_line:
               if line.product_id:
                   transfer_line = {
                       'transfer_id': transfer_id.id,
                       'product_id': line.product_id.id,
                       'state': 'pending',
                       'invoice_state': 'no',
                       'sale_line_id': line.id,
                       'uxb': line.product_packaging_id.qty or False,
                       'qty_demand': line.product_uom_qty or 0,
                   }

                   transfer_lines_list.append(transfer_line)
            
            self.env['wms.transfer.line'].create(transfer_lines_list)

            record.transfer_id = transfer_id.id

        return

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