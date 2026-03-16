# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import base64
import io
from collections import defaultdict
import logging
from openpyxl import load_workbook

_logger = logging.getLogger(__name__)


class ImportSaleOrderMasiveWizard(models.TransientModel):
    _name = 'import.sale.order.masive.wizard'
    _description = 'Wizard: Importar Pedido de Venta Masivo'

    file = fields.Binary(string='Archivo Excel', required=True)
    filename = fields.Char(string='Nombre del Archivo')
    sheet_name = fields.Char(string='Hoja', default='Sheet1')

    company_default_id = fields.Many2one(
        'res.company',
        string='Empresa por Defecto',
        help='Si se completa, fuerza esta empresa para todos los pedidos.'
    )

    log = fields.Text(string='Log', readonly=True)
    validated_line_count = fields.Integer(string='Líneas válidas', readonly=True)
    created_order_count = fields.Integer(string='Pedidos creados', readonly=True)

    def _normalize(self, value):
        if value is None:
            return ''
        return str(value).strip()

    def _float_or_zero(self, value):
        if value in (None, '', False):
            return 0.0
        try:
            return float(value)
        except Exception:
            return 0.0

    def _load_excel_sheet(self):
        self.ensure_one()

        if not self.file:
            raise UserError(_('Debes cargar un archivo Excel.'))

        try:
            content = base64.b64decode(self.file)
            wb = load_workbook(io.BytesIO(content), data_only=False)
        except Exception as e:
            raise UserError(_('No se pudo leer el archivo Excel:\n%s') % e)

        if self.sheet_name not in wb.sheetnames:
            raise UserError(_('No existe la hoja "%s". Hojas disponibles: %s') % (
                self.sheet_name, ', '.join(wb.sheetnames)
            ))

        return wb[self.sheet_name]

    def _read_sheet1_rows(self):
        """
        Lee la hoja Sheet1 con este formato:
        A Cliente
        B Dirección de entrega
        C Condición de venta
        D Plazos de pago
        E Términos y condiciones
        F Notas Internas
        G Descuento Rubro
        H Descuento
        I Producto
        J Cantidad
        K Company Default

        Las filas heredan contexto de filas anteriores si vienen vacías.
        """
        self.ensure_one()
        ws = self._load_excel_sheet()

        rows = []
        current = {
            'cliente': '',
            'direccion_entrega': '',
            'condicion_venta': '',
            'plazos_pago': '',
            'terminos_condiciones': '',
            'notas_internas': '',
            'descuento_rubro': '',
            'descuento': 0.0,
            'company_default': '',
        }

        # Empieza en fila 2 porque fila 1 es encabezado
        for row_idx in range(2, ws.max_row + 1):
            cliente = self._normalize(ws[f'A{row_idx}'].value)
            direccion_entrega = self._normalize(ws[f'B{row_idx}'].value)
            condicion_venta = self._normalize(ws[f'C{row_idx}'].value)
            plazos_pago = self._normalize(ws[f'D{row_idx}'].value)
            terminos_condiciones = self._normalize(ws[f'E{row_idx}'].value)
            notas_internas = self._normalize(ws[f'F{row_idx}'].value)
            descuento_rubro = self._normalize(ws[f'G{row_idx}'].value)
            descuento = ws[f'H{row_idx}'].value
            producto_codigo = self._normalize(ws[f'I{row_idx}'].value)
            cantidad = ws[f'J{row_idx}'].value
            company_default = self._normalize(ws[f'K{row_idx}'].value)

            # Saltar fila vacía total
            if not any([
                cliente, direccion_entrega, condicion_venta, plazos_pago,
                terminos_condiciones, notas_internas, descuento_rubro,
                producto_codigo, cantidad, company_default
            ]):
                continue

            # Herencia de contexto cabecera
            if cliente:
                current['cliente'] = cliente
            if direccion_entrega:
                current['direccion_entrega'] = direccion_entrega
            if condicion_venta:
                current['condicion_venta'] = condicion_venta
            if plazos_pago:
                current['plazos_pago'] = plazos_pago
            if terminos_condiciones:
                current['terminos_condiciones'] = terminos_condiciones
            if notas_internas:
                current['notas_internas'] = notas_internas
            if descuento_rubro:
                current['descuento_rubro'] = descuento_rubro
            if descuento not in (None, '', False):
                current['descuento'] = self._float_or_zero(descuento)
            if company_default:
                current['company_default'] = company_default

            # Solo se importa si hay producto y cantidad
            if producto_codigo and cantidad not in (None, '', False):
                rows.append({
                    'excel_row': row_idx,
                    'cliente': current['cliente'],
                    'direccion_entrega': current['direccion_entrega'],
                    'condicion_venta': current['condicion_venta'],
                    'plazos_pago': current['plazos_pago'],
                    'terminos_condiciones': current['terminos_condiciones'],
                    'notas_internas': current['notas_internas'],
                    'descuento_rubro': current['descuento_rubro'],
                    'descuento': current['descuento'],
                    'producto_codigo': producto_codigo,
                    'cantidad': self._float_or_zero(cantidad),
                    'company_default': current['company_default'],
                })

        if not rows:
            raise UserError(_('No se encontraron líneas importables en la hoja %s.') % self.sheet_name)

        return rows

    def _build_master_data(self, rows):
        partner_names = set()
        shipping_names = set()
        product_codes = set()
        company_names = set()

        for row in rows:
            if row['cliente']:
                partner_names.add(row['cliente'])
            if row['direccion_entrega']:
                shipping_names.add(row['direccion_entrega'])
            if row['producto_codigo']:
                product_codes.add(str(row['producto_codigo']).strip())
            if row['company_default']:
                company_names.add(row['company_default'])

        partners = self.env['res.partner'].search([('name', 'in', list(partner_names))])
        products = self.env['product.product'].search([('default_code', 'in', list(product_codes))])
        companies = self.env['res.company'].search([('name', 'in', list(company_names))]) if company_names else self.env['res.company']

        partner_map = {p.name.strip(): p for p in partners if p.name}
        product_map = {p.default_code.strip(): p for p in products if p.default_code}
        company_map = {c.name.strip(): c for c in companies if c.name}

        return {
            'partner_map': partner_map,
            'product_map': product_map,
            'company_map': company_map,
        }

    def _resolve_company(self, row, master_data):
        if self.company_default_id:
            return self.company_default_id

        company_name = (row.get('company_default') or '').strip()
        if company_name and company_name in master_data['company_map']:
            return master_data['company_map'][company_name]

        return self.env.company

    def _resolve_shipping_partner(self, row, partner):
        shipping_name = (row.get('direccion_entrega') or '').strip()
        if not shipping_name:
            return partner

        shipping = self.env['res.partner'].search([
            ('name', '=', shipping_name),
            ('parent_id', '=', partner.id),
        ], limit=1)

        if shipping:
            return shipping

        shipping = self.env['res.partner'].search([
            ('name', '=', shipping_name),
        ], limit=1)

        return shipping or partner

    def _get_rubro_from_product(self, product):
        categ = product.categ_id
        return (categ.parent_id or categ).name if categ else ''

    def _build_group_key(self, row, partner, shipping, company, product):
        tipo = (row.get('condicion_venta') or '').strip().upper()
        rubro_real = self._get_rubro_from_product(product)

        if tipo == 'TIPO 3':
            return (
                partner.id,
                shipping.id if shipping else False,
                company.id,
                tipo,
            )

        return (
            partner.id,
            shipping.id if shipping else False,
            company.id,
            tipo,
            rubro_real,
        )

    def _prepare_order_vals(self, row, partner, shipping, company):
        note_parts = []
        if row.get('plazos_pago'):
            note_parts.append('Plazos de pago: %s' % row['plazos_pago'])
        if row.get('terminos_condiciones'):
            note_parts.append('Términos y condiciones: %s' % row['terminos_condiciones'])
        if row.get('notas_internas'):
            note_parts.append('Notas internas: %s' % row['notas_internas'])

        return {
            'partner_id': partner.id,
            'partner_shipping_id': shipping.id if shipping else partner.id,
            'company_id': company.id,
            'note': '\n'.join(note_parts) if note_parts else False,
            'client_order_ref': False,
            'origin': 'IMPORT MASIVO',
        }

    def _prepare_order_line_vals(self, row, product):
        qty = row.get('cantidad') or 0.0
        if qty <= 0:
            raise UserError(_('Fila %s: la cantidad debe ser mayor a 0.') % row['excel_row'])

        return {
            'product_id': product.id,
            'name': product.get_product_multiline_description_sale() or product.display_name,
            'product_uom_qty': qty,
            'discount': row.get('descuento') or 0.0,
        }

    def action_validate_file(self):
        self.ensure_one()

        rows = self._read_sheet1_rows()
        master_data = self._build_master_data(rows)

        errors = []

        for row in rows:
            partner = master_data['partner_map'].get((row['cliente'] or '').strip())
            if not partner:
                errors.append(_('Fila %s: no se encontró el cliente "%s".') % (
                    row['excel_row'], row['cliente']
                ))

            product = master_data['product_map'].get((row['producto_codigo'] or '').strip())
            if not product:
                errors.append(_('Fila %s: no se encontró el producto "%s".') % (
                    row['excel_row'], row['producto_codigo']
                ))

            if (row.get('cantidad') or 0.0) <= 0:
                errors.append(_('Fila %s: cantidad inválida.') % row['excel_row'])

        if errors:
            self.write({
                'state': 'draft',
                'validated_line_count': 0,
                'log': '\n'.join(errors),
            })
            raise UserError(_('Se encontraron errores:\n\n%s') % '\n'.join(errors[:80]))

        self.write({
            'state': 'validated',
            'validated_line_count': len(rows),
            'log': _('Archivo validado correctamente. Líneas detectadas: %s') % len(rows),
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }

    def action_import_file(self):
        self.ensure_one()

        rows = self._read_sheet1_rows()
        master_data = self._build_master_data(rows)

        SaleOrder = self.env['sale.order'].with_context(
            tracking_disable=True,
            mail_create_nolog=True,
            mail_notrack=True,
        )

        grouped = defaultdict(lambda: {
            'header': False,
            'lines': [],
        })

        errors = []

        for row in rows:
            try:
                partner = master_data['partner_map'].get((row['cliente'] or '').strip())
                if not partner:
                    raise UserError(_('Fila %s: cliente no encontrado "%s".') % (
                        row['excel_row'], row['cliente']
                    ))

                product = master_data['product_map'].get((row['producto_codigo'] or '').strip())
                if not product:
                    raise UserError(_('Fila %s: producto no encontrado "%s".') % (
                        row['excel_row'], row['producto_codigo']
                    ))

                shipping = self._resolve_shipping_partner(row, partner)
                company = self._resolve_company(row, master_data)

                group_key = self._build_group_key(row, partner, shipping, company, product)

                if not grouped[group_key]['header']:
                    grouped[group_key]['header'] = self._prepare_order_vals(
                        row, partner, shipping, company
                    )

                grouped[group_key]['lines'].append(
                    self._prepare_order_line_vals(row, product)
                )

            except Exception as e:
                errors.append(str(e))

        if errors:
            self.write({'log': '\n'.join(errors)})
            raise UserError(_('Errores antes de importar:\n\n%s') % '\n'.join(errors[:80]))

        created_orders = self.env['sale.order']

        for group_key, data in grouped.items():
            with self.env.cr.savepoint():
                order = SaleOrder.create(data['header'])
                order.write({
                    'order_line': [(0, 0, vals) for vals in data['lines']]
                })
                created_orders |= order

        self.write({
            'state': 'done',
            'validated_line_count': len(rows),
            'created_order_count': len(created_orders),
            'log': _('Importación finalizada. Pedidos creados en borrador: %s') % len(created_orders),
        })

        action = self.env.ref('sale.action_orders').read()[0]
        action['domain'] = [('id', 'in', created_orders.ids)]
        return action