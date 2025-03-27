# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime,date,timedelta
from dateutil import relativedelta
from io import StringIO
import base64
import csv
import logging

_logger = logging.getLogger(__name__)

class AccountExportTax(models.Model):
    _name = 'account.export.tax'
    _description = 'account export tax'

    name = fields.Char('Referencia')
    date = fields.Date('Fecha')
    nif = fields.Char('CUIT')
    partner_id = fields.Many2one('res.partner','Razon Social')
    company_id = fields.Many2one('res.company','Compañía')
    amount = fields.Float('Monto Retencion')
    amount_base = fields.Float('Monto Base')
    tax_withholding_id = fields.Many2one('account.tax','Impuesto Retencion')
    withholding_number = fields.Char('Numero Retencion')
    export_id = fields.Many2one('account.export.sircar','Exportacion Sircar')


class AccountExportSircar(models.Model):
    _name = 'account.export.sircar'
    _description = 'account export sircar'

    name = fields.Char('Name')
    date_from = fields.Date('Fecha desde')
    date_to = fields.Date('Fecha hasta')
    export_sircar_data = fields.Text('Contenidos archivo SIRCAR')
    company_id = fields.Many2one('res.company','Compañía')
    state = fields.Selection([('draft','Borrador'),('done','Hecho'),],string='Estado',default='draft',copy=False,readonly=False)


    @api.depends('export_sircar_data')
    def _compute_files(self):
        self.ensure_one()
        # segun vimos aca la afip espera "ISO-8859-1" en vez de utf-8
        # http://www.planillasutiles.com.ar/2015/08/
        # como-descargar-los-archivos-de.html
        #if self.export_sircar_data:
        self.export_sircar_filename = _('Sircar_%s_%s.txt') % (str(self.date_from),str(self.date_to),)
        if self.export_sircar_data:
           self.export_sircar_file = base64.encodestring(self.export_sircar_data.encode('ISO-8859-1'))

    export_sircar_filename = fields.Char('Archivo_SIRCAR',compute='_compute_files')
    export_sircar_file = fields.Binary('Archivo_SIRCAR',readonly=True)

    def get_lines_of_group(self, type_tax_use, group):
        move_line_obj = self.env['account.move.line']
        tax_obj = self.env['account.tax']
        retencion_ids = tax_obj.search([('type_tax_use', 'in', [type_tax_use]),
                                        ('tax_group_id.name', 'ilike', group)
                                        ])
        return retencion_ids

    def get_withholding_payments(self):
        """ Obtiene los pagos a proveedor que son retenciones y que
            estan en el periodo seleccionado
        """
        #ref_retencion_group = self.env.ref('l10n_ar.tax_group_retencion_iibb')
        retencion_ids = self.get_lines_of_group(type_tax_use='supplier', group='iibb')
        return retencion_ids


    def compute_sircar_data(self):
        self.ensure_one()
        windows_line_ending = '\r' + '\n'
        if self.company_id:
            payments = self.env['account.payment'].search([('payment_type','=','outbound'),('state','not in',['cancel','draft']),('company_id','=',self.company_id.id)])
        else:
            payments = self.env['account.payment'].search([('payment_type','=','outbound'),('state','not in',['cancel','draft'])])
        #,('payment_date','<=',self.date_to),('payment_date','>=',self.date_from)])
        retencion_ids = self.get_withholding_payments()
        payments = payments.search([('tax_withholding_id','in',retencion_ids.ids)])
        string = ''
        n = 0
        for payment in payments:
            if payment.date < self.date_from or payment.date > self.date_to:
                continue
            _logger.info(' %s %s ' % (payment.payment_group_id.regimen_ganancias_id,payment.withholding_number) )
            if not (payment.payment_group_id.regimen_ganancias_id) or not payment.withholding_number:
                continue
            #if 'Retenciones' not in payment.journal_id.name:
            #    continue
            n += 1
            # 1er campo: numero incremental
            string = string + str(n).zfill(5) + ','

            # 2do campo codigo de operacion 1 tomado de ejemplo XLS
            string = string + '1,1' + ','

            # 3er campo nro de comprobante - imprimimos nro de retenciontring = string + payment_data['withholding_number'].zfill(12)
            string = string  + payment.payment_group_id.name[5:9].zfill(4) + payment.payment_group_id.name[10:].zfill(8) + ','

            # 4to campo - nro de CUIT
            string = string + payment.partner_id.vat.zfill(11) + ','

            # 5to campo - fecha de emision de la retencion
            string = string + str(payment.payment_date)[8:10] + '/' + str(payment.payment_date)[5:7] + '/' + str(payment.payment_date)[:4]  + ','

            # 6to monto base sujeto a retencion
            if payment.withholding_base_amount>=payment.amount:
                cadena = "%.2f"%payment.withholding_base_amount
            else:
               # cadena = "%.2f"%payment.amount
                cadena = "%.2f"%payment.withholding_base_amount
            #cadena = cadena.replace(',','.')
            string = string + cadena.zfill(12) + ','

            # 7mo campo - porcentaje retencion
            if payment.withholding_base_amount>=payment.amount and payment.amount>0:
                cadena = "%.2f" % (payment.amount/payment.withholding_base_amount*100)
            else:
               # cadena = "%.2f"%payment.amount
                cadena = "0.00"
            #cadena = cadena.replace('.',',')
            string = string + cadena.zfill(6) + ','

            # 8vo campo - monto retenido
            if payment.amount > 0:
                cadena = "%.2f"%payment.amount
                #cadena = cadena.replace('.',',')
            else:
                cadena = '0.00'
            #string = string + cadena.rjust(12)
            string = string + cadena.zfill(12)  + ','
            #string = string + str(payment_data['withholding_base_amount']).zfill(16)
            #  Campo - Codigo de Impuesto - 217 tomado de tabla de codigos de sircar
            #string = string + str(payment.tax_withholding_id.tax_group_id.l10n_ar_vat_afip_code).zfill(4)[:4]

            # 9no campo - codigo de tipo de regimen tomado de ejemplo XLS
            string = string + '515' + ','

            # 10mo campo - codigo de Jurisdiccion tomado de ejemplo XLS
            string = string + '921'
            # CRLF
            string = string + windows_line_ending

        self.export_sircar_data = string
        self._compute_files()

    def create_table_ret(self):
        self.ensure_one()
        if self.company_id:
            payments = self.env['account.payment'].search([('payment_type','=','outbound'),('state','not in',['cancel','draft']),('company_id','=',self.company_id.id)])
        else:
            payments = self.env['account.payment'].search([('payment_type','=','outbound'),('state','not in',['cancel','draft'])])

        retencion_ids = self.get_withholding_payments()
        payments = payments.search([('tax_withholding_id','in',retencion_ids.ids)])

        n = 0
        for payment in payments:
            if payment.payment_date < self.date_from or payment.payment_date > self.date_to:
                continue
            if not (payment.communication or payment.payment_group_id.regimen_ganancias_id) or not payment.withholding_number:
                continue
            self.env['account.export.tax'].sudo().create({
                                                          'name':payment.payment_group_id.name,
                                                          'date':payment.payment_date,
                                                          'nif':payment.partner_id.vat,
                                                          'partner_id':payment.partner_id.id,
                                                          'company_id':payment.payment_group_id.company_id.id,
                                                          'amount':payment.amount,
                                                          'amount_base':payment.withholding_base_amount,
                                                          'tax_withholding_id':payment.tax_withholding_id.id,
                                                          'withholding_number':payment.withholding_number,
                                                          'export_id':self.id})

    def set_done(self):
        self.create_table_ret()
        self.state = 'done'

    def set_draft(self):
        self.env['account.export.tax'].sudo().search([('export_id','=',self.id)]).unlink()
        self.state = 'draft'


'''
    def compute_sircar_data(self):
        self.ensure_one()
        if self.company_id:
            payments = self.env['account.payment'].search([('payment_type','=','outbound'),('state','not in',['cancel','draft']),('company_id','=',self.company_id.id)])
        else:
            payments = self.env['account.payment'].search([('payment_type','=','outbound'),('state','not in',['cancel','draft'])])

        retencion_ids = self.get_withholding_payments()
        payments = payments.search([('tax_withholding_id','in',retencion_ids.ids)])

        csv_data = StringIO()
        csv_writer = csv.writer(csv_data)

        n = 0
        for payment in payments:
            if payment.payment_date < self.date_from or payment.payment_date > self.date_to:
                continue
            if not (payment.communication or payment.payment_group_id.regimen_ganancias_id) or not payment.withholding_number:
                continue

            n += 1
            row = []

            # 1st column: incremental number
            row.append(str(n).zfill(4))
            # 2nd column: code of operation (1 taken as an example)
            row.append('1')
            # 3rd column: number of receipt
            row.append(payment.payment_group_id.name[5:9].zfill(4) + payment.payment_group_id.name[10:].zfill(8))
            # 4th column: number of CUIT
            row.append(payment.partner_id.vat.zfill(11))
            # 5th column: date of withholding
            row.append(str(payment.payment_date)[8:10] + '/' + str(payment.payment_date)[5:7] + '/' + str(payment.payment_date)[:4])
            # 6th column: amount
            row.append('%.2f' % payment.amount)
            # 7th column: withholding percentage
            if payment.withholding_base_amount >= payment.amount and payment.amount > 0:
                row.append('%.2f' % (payment.amount / payment.withholding_base_amount * 100))
            else:
                row.append('0.00')
            # 8th column: calculation base
            row.append('%.2f' % payment.withholding_base_amount)
            # 9th column: code of operation (1 taken as an example)
            row.append('515')
            # 10th column: code of operation (1 taken as an example)
            row.append('921')

            csv_writer.writerow(row)

        csv_binary_data = base64.b64encode(csv_data.getvalue().encode('utf-8'))
        self.export_sircar_csv = csv_binary_data
'''
