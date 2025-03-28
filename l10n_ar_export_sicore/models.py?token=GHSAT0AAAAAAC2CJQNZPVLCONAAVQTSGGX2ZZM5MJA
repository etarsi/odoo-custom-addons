# -*- coding: utf-8 -*-
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime,date,timedelta
from dateutil import relativedelta
import base64
import logging

_logger = logging.getLogger(__name__)

class AccountExportSicore(models.Model):
    _name = 'account.export.sicore'
    _description = 'account.export.sicore'

    name = fields.Char('Name')
    date_from = fields.Date('Fecha desde')
    date_to = fields.Date('Fecha hasta')
    export_sicore_data = fields.Text('Contenidos archivo SICORE')
    company_id = fields.Many2one('res.company','Compañía')


    @api.depends('export_sicore_data')
    def _compute_files(self):
        self.ensure_one()
        # segun vimos aca la afip espera "ISO-8859-1" en vez de utf-8
        # http://www.planillasutiles.com.ar/2015/08/
        # como-descargar-los-archivos-de.html
        #if self.export_sicore_data:
        self.export_sicore_filename = _('Sicore_%s_%s.txt') % (str(self.date_from),str(self.date_to),)
        if self.export_sicore_data:
           self.export_sicore_file = base64.encodestring(self.export_sicore_data.encode('ISO-8859-1'))

    export_sicore_filename = fields.Char('Archivo_SICORE',compute='_compute_files')
    export_sicore_file = fields.Binary('Archivo_SICORE',readonly=True)

    def get_lines_of_group(self, type_tax_use, group):
        move_line_obj = self.env['account.move.line']
        tax_obj = self.env['account.tax']
        retencion_ids = tax_obj.search([('type_tax_use', 'in', [type_tax_use]),
                                        ('tax_group_id', '=', group.id)
                                        ])
        return retencion_ids

    def get_withholding_payments(self):
        """ Obtiene los pagos a proveedor que son retenciones y que
            estan en el periodo seleccionado
        """
        ref_retencion_group = self.env.ref('l10n_ar_ux.tax_group_retencion_ganancias')
        retencion_ids = self.get_lines_of_group(type_tax_use='supplier', group=ref_retencion_group)
        return retencion_ids

    def get_withholding_iva(self):
        ref_retencion_iva_group = self.env.ref('l10n_ar_ux.tax_group_retencion_iva')
        move_retencion_iva_ids = self.get_lines_of_group(type_tax_use='supplier', group=ref_retencion_iva_group)
        return move_retencion_iva_ids


    def compute_sicore_data(self):
        self.ensure_one()
        windows_line_ending = '\r' + '\n'
        retencion_ids = self.get_withholding_payments() + self.get_withholding_iva()
        #retencion_ids = self.get_withholding_iva()
        if self.company_id:
            _logger.info(self.company_id)
            payments = self.env['account.payment'].search([('payment_type','=','outbound'),('state','not in',['cancelled','draft']),('company_id','=',self.company_id.id),('tax_withholding_id','in',retencion_ids.ids)])
        else:
            payments = self.env['account.payment'].search([('payment_type','=','outbound'),('state','not in',['cancelled','draft']),('tax_withholding_id','in',retencion_ids.ids)])
        #payments = payments.search([('tax_withholding_id','in',retencion_ids.ids)])
        string = ''
        for payment in payments:
            if payment.payment_date < self.date_from or payment.payment_date > self.date_to:
                continue
            if not (payment.communication or payment.payment_group_id.regimen_ganancias_id) or not payment.withholding_number:
                continue
            #if 'Retenciones' not in payment.journal_id.name:
            #    continue
            # 1er campo codigo de comprobante: pago 06
            string = string + '06'
            # 2do campo fecha de emision de comprobante
            string = string + str(payment.payment_date)[8:10] + '/' + str(payment.payment_date)[5:7] + '/' + str(payment.payment_date)[:4]
            # 3er campo nro de comprobante - imprimimos nro de retenciontring = string + payment_data['withholding_number'].zfill(16)
            string = string + '    ' + payment.payment_group_id.name[5:9].zfill(4) + payment.payment_group_id.name[10:].zfill(8)
            # 4to campo amount
            if payment.payment_group_id.payments_amount > 0:
                #cadena = str(round(payment_data['withholding_base_amount'],2))
                #cadena = "%.2f"%payment.payment_group_id.to_pay_amount
                cadena = "%.2f"%payment.payment_group_id.payments_amount
                cadena = cadena.replace('.',',')
            else:
                cadena = '0,00'
            #string = string + cadena.rjust(16)
            string = string + cadena.zfill(16)
            #string = string + str(payment_data['withholding_base_amount']).zfill(16)
            # 5to Campo - Codigo de Impuesto - 217 tomado de tabla de codigos de sicore
            string = string + '0217'
            #string = string + str(payment.tax_withholding_id.tax_group_id.l10n_ar_vat_afip_code).zfill(4)[:4]
            # 6to campo - Codigo de regimen 078 tomado de tabla de codigos de sicore - Enajenacion de bienes de cambio
            #string = string + '078'
            #string = string + partner_data[0]['default_regimen_ganancias_id'][1].zfill(3)[:3]
            if payment.communication:
                concepto = int(payment.communication[:3])
            else:
                concepto = int(payment.payment_group_id.regimen_ganancias_id.codigo_de_regimen[:3])
            string = string + str(concepto).zfill(3)
            # 7mo campo - codigo de operacion 1 tomado de ejemplo XLS
            string = string + '1'
            # 8vo campo - base de calculo (52 a 65)
            if payment.withholding_base_amount>=payment.amount:
                cadena = "%.2f"%payment.withholding_base_amount
            else:
               # cadena = "%.2f"%payment.amount
                cadena = "%.2f"%payment.withholding_base_amount
            cadena = cadena.replace('.',',')
            string = string + cadena.zfill(14)
            # 9vo campo - fecha de emision de la retencion (66 a 75)
            string = string + str(payment.payment_date)[8:10] + '/' + str(payment.payment_date)[5:7] + '/' + str(payment.payment_date)[:4]
            # (76 a 77) codigo de condicioon
            if payment.tax_withholding_id.tax_group_id.tax_type == 'withholdings':
                string = string + '01'
            elif payment.tax_withholding_id.tax_group_id.tax_type == 'perception':
                string = string + '02'
            else:
                string = string + '99'
            #(78 a 78) - retencion a sujetos suspendidos
            string = string + ' '
            # 11mo campo - importe retencion - 79 a 92
            #    cadena = str(round(payment_data['amount'],2))
            cadena = "%.2f"%payment.amount
            cadena = cadena.replace('.',',')
            #string = string + str(payment_data['amount']).zfill(14)
            string = string + cadena.zfill(14)
            # 12vo campo - porcentaje de la exclusion
            cadena = '000,00'
            string = string + cadena
            # 13vo campo - fecha de emision del boletin
            #string = string + payment_data['payment_date'][8:10] + '/' + payment_data['payment_date'][5:7] + '/' + payment_data['payment_date'][:4]
            #string = string + ' '.rjust(10)
            string = string + str(payment.payment_date)[8:10] + '/' + str(payment.payment_date)[5:7] + '/' + str(payment.payment_date)[:4]
            # 14 tipo de documento del retenido
            string = string + '80'
            # 15vo campo - ro de CUIT
            if not payment.partner_id.vat:
                 raise ValidationError("Indique la CUIT del contacto '%s' " % payment.partner_id.name)
            string = string + payment.partner_id.vat + '         '
            # 16vo campo nro certificado original
            string = string + str(payment.withholding_number).zfill(14)
            #string = string + '0'.zfill(14)
            # Denominacion del ordenante
            #string = string + partner_data[0]['name'][:30].ljust(30)
            string = string + ' '.ljust(30)
            # Acrecentamiento
            string = string + '0'
            # cuit pais retenido
            string = string + '00000000000'
            # cuit del ordenante
            string = string + '00000000000'
            # CRLF
            _logger.info(string)
            string = string + windows_line_ending

        self.export_sicore_data = string
        self._compute_files()

