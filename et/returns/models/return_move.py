from odoo import models, fields, api, _
from odoo.http import request, content_disposition
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO
from datetime import datetime
from odoo.exceptions import UserError, AccessError
import logging
import math
import requests
from itertools import groupby
from datetime import timedelta
from odoo.tools import defaultdict
from odoo.models import BaseModel
from odoo.exceptions import UserError
import pprint

_logger = logging.getLogger(__name__)

class ReturnMove(models.Model):
    _name = 'return.move'

    name = fields.Char(string="Nombre", required=True, default="/")
    partner_id = fields.Many2one('res.partner', string="Cliente")
    sale_id = fields.Many2one('sale.order', string="Pedido de Venta")
    cause = fields.Selection(string="Motivo", default=False, selection=[
        ('error', 'Producto Erróneo'),
        ('broken','Producto Roto'),
        ('no', 'No lo quiere'),
        ('expensive', 'Muy caro'),
        ('bad', 'No lo pudo vender')])
    info = fields.Text(string="Información adicional")
    date = fields.Date(string="Fecha de Recepción", default=fields.Date.today)
    state = fields.Selection(string="Estado", default='draft', selection=[
        ('draft','Borrador'), 
        ('pending', 'Pendiente'), 
        ('inprogress', 'En Proceso'), 
        ('confirmed', 'Confirmado'), 
        ('done', 'Hecho')
    ])
    move_lines = fields.One2many('return.move.line', 'return_move', string="Devoluciones Sanas")
    price_total = fields.Float(string="Total", compute="_compute_price_total")
    company_id = fields.Many2one('res.company', string="Compañía")
    wms_code = fields.Char("Código WMS")


    credit_notes = fields.One2many(string="Notas de Crédito", comodel_name="account.move", inverse_name="return_id")
    credit_count = fields.Integer(string="Notas de Crédito", compute="_compute_credit_count")


    def action_confirm(self):
        for record in self:
            record.state = 'confirmed'


    def action_create_credit_notes(self):
        AccountMove = self.env['account.move']

        for rm in self:
            if not rm.move_lines:
                raise UserError(_("La devolución no tiene líneas."))

            groups = defaultdict(list)

            for line in rm.move_lines:
                if not line.invoice_line_id or not line.invoice_id:
                    line.update_prices()

                if not line.invoice_line_id or not line.invoice_id:
                    raise UserError(_(
                        "No se encontró factura/línea de factura para el producto %s."
                    ) % (line.product_id.display_name,))

                inv = line.invoice_id
                if inv.move_type != 'out_invoice' or inv.state != 'posted':
                    raise UserError(_("Factura inválida (debe ser factura cliente posteada): %s") % inv.display_name)

                company_id = inv.company_id.id
                groups[(company_id, inv.id)].append(line)

            created_moves = AccountMove

            for (company_id, invoice_id), return_lines in groups.items():
                invoice = AccountMove.browse(invoice_id)
                company = invoice.company_id

                journal = self.env['account.journal'].search([
                    ('type', '=', 'sale'),
                    ('company_id', '=', company.id),
                    ('code', '=', '00010')
                ], limit=1)
                if not journal:
                    raise UserError(_("No encontré un diario de Ventas para la compañía %s") % company.display_name)


                if invoice.l10n_latam_document_type_id.code == '1':
                    document_type = self.env['l10n_latam.document.type'].browse(3)
                elif invoice.l10n_latam_document_type_id.code == '201':
                    document_type = self.env['l10n_latam.document.type'].browse(111)

                cn = rm._create_cn_without_x2many(company, journal, document_type, invoice, return_lines)
                created_moves |= cn
            rm.credit_notes = [(6, 0, created_moves.ids)]

            return rm._action_open_credit_notes(created_moves)


    def _assert_vals_clean(self, obj, path="vals"):
        if isinstance(obj, BaseModel):
            raise UserError("VALS INVÁLIDOS: recordset en %s (%s)" % (path, obj._name))
        if isinstance(obj, dict):
            for k, v in obj.items():
                self._assert_vals_clean(v, "%s.%s" % (path, k))
        elif isinstance(obj, (list, tuple)):
            for i, v in enumerate(obj):
                self._assert_vals_clean(v, "%s[%s]" % (path, i))


    def _debug_find_bad_key_for_new(self, company, clean_ctx, cn_vals):
        Move = self.env['account.move'].with_company(company).with_context(clean_ctx)

        # probar de a una key
        for k in list(cn_vals.keys()):
            try:
                Move.new({k: cn_vals[k]})
            except Exception as e:
                raise UserError("DEBUG: new() revienta con key='%s' value=%r\nERROR=%s" % (k, cn_vals[k], e))

        # probar acumulativo (por si es combinación de dos)
        acc = {}
        for k in list(cn_vals.keys()):
            acc[k] = cn_vals[k]
            try:
                Move.new(acc)
            except Exception as e:
                raise UserError("DEBUG: new() revienta al agregar key='%s' value=%r\nACC=%r\nERROR=%s" % (k, cn_vals[k], acc, e))

        raise UserError("DEBUG: new() NO revienta con ninguna key individual (es combinación rara).")


    def _create_cn_without_x2many(self, company, journal, document_type, invoice, return_lines):
        AccountMove = self.env['account.move']
        AML = self.env['account.move.line']

        # clean_ctx = dict(self.env.context)
        # for k in list(clean_ctx.keys()):
        #     if k.startswith('default_'):
        #         clean_ctx.pop(k, None)

        # clean_ctx.update({
        #     'default_move_type': 'out_refund',
        #     'check_move_validity': False,
        #     'skip_invoice_sync': True,
        #     'mail_create_nosubscribe': True,
        #     'tracking_disable': True,
        # })

        cn_vals = {
            'move_type': 'out_refund',
            'company_id': invoice.company_id.id,
            'journal_id': journal.id,
            'partner_id': invoice.partner_id.id,
            'partner_shipping_id': invoice.partner_shipping_id.id or invoice.partner_id.id,
            'currency_id': invoice.currency_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': fields.Date.context_today(self),
            'invoice_payment_term_id': invoice.invoice_payment_term_id.id or False,
            'fiscal_position_id': invoice.fiscal_position_id.id or False,

            'invoice_origin': invoice.invoice_origin or invoice.name,
            'payment_reference': invoice.payment_reference or invoice.name,
            'ref': f"Devolución {self.name} - Factura {invoice.name}",
            'reversed_entry_id': invoice.id,
        }
       
        cn_vals.pop('line_ids', None)

        cn = AccountMove.with_company(company).create(cn_vals)
        # cn = AccountMove.with_company(company).with_context(clean_ctx).create(cn_vals)
        lines_cmds = []
        for rline in return_lines:
            inv_line = rline.invoice_line_id
            qty = rline.quantity_total
            if not qty or qty <= 0:
                continue

            lines_cmds.append((0, 0, {
                'product_id': inv_line.product_id.id or False,
                'name': inv_line.name or inv_line.product_id.display_name,
                'quantity': qty,
                'product_uom_id': (inv_line.product_uom_id.id or inv_line.product_id.uom_id.id),
                'price_unit': inv_line.price_unit or 0.0,
                'discount': inv_line.discount or 0.0,
                'account_id': inv_line.account_id.id,                 # importante
                'tax_ids': [(6, 0, inv_line.tax_ids.ids or [])],      # importante
            }))

        cn.write({'invoice_line_ids': lines_cmds})

        # Forzar recomputes típicos de factura
        cn._recompute_dynamic_lines(recompute_all_taxes=True)
        cn._compute_amount()


        return cn



    def _action_open_credit_notes(self, credit_notes):
        action = self.env.ref('account.action_move_out_refund_type').read()[0]
        action['domain'] = [('id', 'in', credit_notes.ids)]
        if len(credit_notes) == 1:
            action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
            action['res_id'] = credit_notes.id
        return action
    
    
    # def _prepare_invoice_line(self, **optional_values):
    #     """
    #     Prepare the dict of values to create the new invoice line for a sales order line.

    #     :param qty: float quantity to invoice
    #     :param optional_values: any parameter that should be added to the returned invoice line
    #     """
    #     self.ensure_one()

    #     res = {
    #         'display_type': False,
    #         'sequence': self.sequence,
    #         'name': self.name,
    #         'product_id': self.product_id.id,
    #         'product_uom_id': self.product_id.uom_id.id,
    #         'quantity': self.quantity_total,
    #         'discount': self.discount,
    #         'price_unit': self.price_unit,
    #         'tax_ids': [(6, 0, self.tax_id.ids)],
            # 'sale_line_ids': [(4, self.invoice_line_id)], # por ahora no interesa actualizar este dato
        # }
        # if self.order_id.analytic_account_id and not self.display_type:
        #     res['analytic_account_id'] = self.order_id.analytic_account_id.id
        # if self.analytic_tag_ids and not self.display_type:
        #     res['analytic_tag_ids'] = [(6, 0, self.analytic_tag_ids.ids)]
        # if optional_values:
            # res.update(optional_values)
        # if self.display_type:
        #     res['account_id'] = False
        # return res

    def _prepare_invoice_base_vals(self, company_id):
        invoice_date_due = fields.Date.context_today(self)

        if self.sale_id.payment_term_id:
            extra_days = max(self.sale_id.payment_term_id.line_ids.mapped('days') or [0])
            invoice_date_due = self.set_due_date_plus_x(extra_days)
        
        
        return {
            'move_type': 'out_refund',
            'partner_id': self.sale_id.partner_invoice_id,
            'partner_shipping_id': self.sale_id.partner_shipping_id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': invoice_date_due,
            'company_id': self.sale_id.company_id.id,
            'currency_id': self.sale_id.company_id.currency_id.id,
            'invoice_origin': self.origin or self.name,
            'payment_reference': self.name,
            'fiscal_position_id': self.sale_id.partner_invoice_id.property_account_position_id.id,
            'invoice_payment_term_id': self.sale_id.payment_term_id,
            'wms_code': self.codigo_wms,
            'pricelist_id': self.sale_id.pricelist_id.id,
            'special_price': self.sale_id.special_price,
        }

    ### COMPUTED ###

    @api.depends('move_lines.price_subtotal')
    def _compute_price_total(self):
        for record in self:
            if record.move_lines:
                record.price_total = sum(record.move_lines.mapped('price_subtotal'))
            else:
                record.price_total = 0


    @api.depends('credit_notes')
    def _compute_credit_count(self):
        for record in self:
            record.credit_count = len(record.credit_notes)

    ### ONCHANGE ###

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        for record in self:
            if record.move_lines:
                record.move_lines.update_prices()


    def action_send_return(self):        
        for record in self:
            
            next_number = self.env['ir.sequence'].sudo().next_by_code('DEV')
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
            }

            provider = record.get_current_provider(record.partner_id)

            payload = {
                "Numero": f'R{next_number}',
                "Factura": "",
                "Fecha": str(record.date),
                "CodigoProveedor": provider['code'],
                "Proveedor": provider['name'],
                "Observacion": "Prueba de Odoo",
                "DocumentoRecepcionTipo": "remito",
                "RecepcionTipo": "devolucion",
                "DocumentoRecepcionDetalleRequest": [
                ]
            }          
            
            
            headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
            response = requests.post('http://api.patagoniawms.com/v1/DocumentoRecepcion', headers=headers, json=payload)

            if response.status_code == 200:
                record.state = 'inprogress'
                record.wms_code = f'R{next_number}'
                record.name = record.get_document_name(next_number)
            else:
                raise UserError(f'Error code: {response.status_code} - Error Msg: {response.text}')


    def get_current_provider(self, partner_id):
        current_provider = {
            'code': "",
            'name': "",
        }
        
        providers = self.get_providers()

        for p in providers:
                if p['Activo']:
                    if p['Descripcion'] == partner_id.name:
                        current_provider['code'] = p['Codigo']
                        current_provider['name'] = p['Descripcion']
                        return current_provider

        if not current_provider['code']:        
            current_provider = self.create_provider(partner_id)
            return current_provider
            

    def get_providers(self):
        
        headers = {}
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        
        response = requests.get('http://api.patagoniawms.com/v1/Proveedor', headers=headers)

        if response.status_code == 200:
            data = response.json()
            return data        
        else:
            raise UserError(f'No se pudo obtener los proveedores de Digip. STATUS_CODE: {response.status_code}')


    def create_provider(self, provider):
        current_provider = {}
        headers = {}
        headers["x-api-key"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
        payload = {
                "Codigo": str(provider.id),
                "Descripcion": provider.name,
                "RequiereControlCiego": True,
                "Activo": True,
                }
        response = requests.post('http://api.patagoniawms.com/v1/Proveedor', headers=headers, json=payload)

        if response.status_code == 204:
            current_provider['code'] = provider.id
            current_provider['name'] = provider.name

            return current_provider
        else:
            raise UserError(f'No se pudo crear el proveedor en Digip. STATUS_CODE: {response.status_code}')
        


    def get_document_name(self, next_number):
        
        name = f'DEV-{next_number}'

        return name




class ReturnMoveLine(models.Model):
    _name = 'return.move.line'

    name = fields.Char(string="Nombre", required=True, default="Remito de prueba")
    return_move = fields.Many2one('return.move', string="Devolución")
    product_id = fields.Many2one('product.product', string="Producto")
    quantity_healthy = fields.Integer(string="Cantidad Sana")
    quantity_broken = fields.Integer(string="Cantidad Rota")
    quantity_total = fields.Integer(string="Total", compute="_compute_quantity_total")
    uxb = fields.Integer(string="UxB")
    bultos = fields.Float(string="Bultos", compute="_compute_bultos")
    price_unit = fields.Float(string="Precio Unitario")
    discount = fields.Float(string="Descuento")
    price_subtotal = fields.Float(string="Precio Subtotal", compute="_compute_subtotal")
    state = fields.Selection(string='State', selection=[('draft','Borrador'), ('confirmed','Confirmado'), ('done', 'Hecho')])
    company_id = fields.Many2one(string="Compañía", comodel_name="res.company")

    invoice_id = fields.Many2one(string="Factura Asociada", comodel_name="account.move")
    invoice_line_id = fields.Many2one(string="Línea de Factura Asociada", comodel_name="account.move.line")


    @api.model
    def create(self, vals):
        res = super().create(vals)

        for record in res:
            record.update_prices()
            record._compute_subtotal()
            record._onchang_product_uxb()
            record._compute_bultos()

        return res


    @api.onchange('product_id')
    def _onchang_product_uxb(self):
        for record in self:
            if record.product_id:
                record.uxb = record.get_product_uxb(record.product_id)


    @api.depends('quantity_healthy', 'quantity_broken')
    def _compute_quantity_total(self):
        for record in self:
            record.quantity_total = record.quantity_healthy + record.quantity_broken

    
    @api.depends('price_unit', 'quantity_total', 'discount')
    def _compute_subtotal(self):
        for record in self:
            record.price_subtotal = record.price_unit * record.quantity_total * record.discount / 100
    

    def update_prices(self):
        for record in self:
            if record.product_id:
                record.invoice_line_id = record.get_last_invoice_line()

                if record.invoice_line_id:
                    record.invoice_id = record.invoice_line_id.move_id.id
                    record.price_unit = record.invoice_line_id.price_unit
                    record.discount = record.invoice_line_id.discount                
                    record.company_id = record.invoice_line_id.company_id.id


                # CONDICIONAL A REVISAR
                # if record.invoice_line_id.company_id.id == 1:
                #     record.price_unit = record.invoice_line_id.price_unit / 1.21
                #     record.company_id = 2
                #     record.discount = record.invoice_line_id.discount
                # else:
                #     record.price_unit = record.invoice_line_id.price_unit
                #     record.company_id = record.invoice_line_id.company_id.id
                #     record.discount = record.invoice_line_id.discount


    def get_last_invoice_line(self):
        for record in self:
            last_invoice_line = self.env['account.move.line'].search([
                ('partner_id', '=', record.return_move.partner_id.id),
                ('product_id', '=', record.product_id.id),
                ('parent_state', '=', 'posted'),                
                ('move_id.move_type', '=', 'out_invoice'),
                ('display_type', '=', False),
            ], order="date desc, move_id desc, id desc", limit=1)

            if last_invoice_line:
                return last_invoice_line
            

    def get_product_uxb(self, product_id):
        if product_id.packaging_ids:
            return product_id.packaging_ids[0].qty
        

    @api.depends('quantity_total')
    def _compute_bultos(self):
        for record in self:
            if record.uxb != 0:
                record.bultos = record.quantity_total / record.uxb
            else:
                record.bultos = 0
