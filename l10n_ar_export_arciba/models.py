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
import re
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)


#########
# helpers
#########


def format_amount(amount, padding=15, decimals=2, sep=""):
    if amount < 0:
        template = "-{:0>%dd}" % (padding - 1 - len(sep))
    else:
        template = "{:0>%dd}" % (padding - len(sep))
    res = template.format(
        int(round(abs(amount) * 10**decimals, decimals)))
    if sep:
        res = "{0}{1}{2}".format(res[:-decimals], sep, res[-decimals:])
    return res

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
    export_id = fields.Many2one('account.export.arciba','Exportacion Sircar')


class AccountExportArciba(models.Model):
    _name = 'account.export.arciba'
    _description = 'account export arciba'

    name = fields.Char('Name')
    date_from = fields.Date('Fecha desde')
    date_to = fields.Date('Fecha hasta')
    export_arciba_data = fields.Text('Contenidos archivo ARCIBA')
    export_arciba_data_credito = fields.Text('Contenidos archivo ARCIBA Credito')
    company_id = fields.Many2one('res.company','Compañía')
    state = fields.Selection([('draft','Borrador'),('done','Hecho'),],string='Estado',default='draft',copy=False,readonly=False)
    move_lines_ids_txt = fields.Text('move_ids')
    move_lines_ids = fields.One2many('account.move.line','id','Movimientos',_compute="list_move_lines")

    def line_move_lines(self):
        return self.env['account.move.line'].search([('id','in',eval(self.move_lines_ids_txt))])



    @api.depends('export_arciba_data','export_arciba_data_credito')
    def _compute_files(self):
        self.ensure_one()
        # segun vimos aca la afip espera "ISO-8859-1" en vez de utf-8
        # http://www.planillasutiles.com.ar/2015/08/
        # como-descargar-los-archivos-de.html
        #if self.export_arciba_data:
        self.export_arciba_filename = 'Perc/Ret IIBB AGIP Aplicadas.txt'
        if self.export_arciba_data:
           self.export_arciba_file = base64.encodestring(self.export_arciba_data.encode('ISO-8859-1'))
        self.export_arciba_filename_credito = 'NC Perc/Ret IIBB AGIP Aplicadas.txt'
        if self.export_arciba_data_credito:
           self.export_arciba_file_credito = base64.encodestring(self.export_arciba_data_credito.encode('ISO-8859-1'))

    export_arciba_filename = fields.Char('Archivo_ARCIBA',compute='_compute_files')
    export_arciba_file = fields.Binary('Archivo_ARCIBA',readonly=True)
    export_arciba_filename_credito = fields.Char('Archivo_ARCIBA_Credito',compute='_compute_files')
    export_arciba_file_credito = fields.Binary('Archivo_ARCIBA_Credito',readonly=True)

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


    #def iibb_aplicado_agip_files_values(self, move_lines):
    def compute_arciba_data(self):
        """ Ver readme del modulo para descripcion del formato. Tambien
        archivos de ejemplo en /doc
        """
        self.ensure_one()
        moves_ids =[]
        if self.company_id.agip_padron_type != 'regimenes_generales':
            raise ValidationError(_(
                'Por ahora solo esta implementado el padrón de Regímenes '
                'Generales, revise la configuración en "Contabilidad / "'
                'Configuración / Ajustes"'))

        ret_perc = ''
        credito = ''

        move_lines_per = self.env['account.move.line'].search([("parent_state", "=", "posted"), ("tax_tag_ids", "in", [19]),("company_id","=",self.company_id.id)])
        move_lines_ret = self.env['account.move.line'].search([("parent_state", "=", "posted"), ("account_id.code", "ilike", '2.1.3.02.030'),("company_id","=",self.company_id.id)])
        move_lines = move_lines_per + move_lines_ret

        company_currency = self.company_id.currency_id
        for line in move_lines.sorted('date'):
            _logger.info('AGIP',line)
            if line.date < self.date_from or line.date > self.date_to:
                continue
            if not line.partner_id:
                continue
            moves_ids.append(line.id)

            # pay_group = payment.payment_group_id
            move = line.move_id
            payment = line.payment_id
            tax = line.tax_line_id
            partner = line.partner_id
            internal_type = line.l10n_latam_document_type_id.internal_type

            if not partner.vat:
                _logger.info('%s' % line)
                raise ValidationError(_(
                    'El partner "%s" (id %s) no tiene número de identificación '
                    'seteada') % (partner.name, partner.id))

            alicuot_line = tax.get_partner_alicuot(partner, line.date)
            if not alicuot_line:
                raise ValidationError(_(
                    'No hay alicuota configurada en el partner '
                    '"%s" (id: %s) %s') % (partner.name, partner.id,tax))

            ret_perc_applied = False
            es_percepcion = False
            # 1 - Tipo de Operación
            if tax.type_tax_use in ['sale', 'purchase']:
                    # tax.amount_type == 'partner_tax':
                es_percepcion = True
                content = '2'
                alicuot = alicuot_line.alicuota_percepcion
            elif tax.type_tax_use in ['customer', 'supplier']:
                    # tax.withholding_type == 'partner_tax':
                content = '1'
                alicuot = alicuot_line.alicuota_retencion

            # notas de credito
            if internal_type == 'credit_note':
                # 2 - Nro. Nota de crédito
                content += '%012d' % int(
                    re.sub('[^0-9]', '', move.l10n_latam_document_number or ''))

                # 3 - Fecha Nota de crédito
                content += fields.Date.from_string(
                    line.date).strftime('%d/%m/%Y')

                # 4 - Monto nota de crédito
                # TODO implementar devoluciones de pagos
                # content += format_amount(
                #     line.move_id.cc_amount_total, 16, 2, ',')
                # la especificacion no lo dice claro pero un errror al importar
                # si, lo que se espera es el importe base, ya que dice que
                # este, multiplicado por la alícuota, debe ser igual al importe
                # a retener/percibir
                taxable_amount = line.tax_base_amount
                content += format_amount(taxable_amount, 16, 2, ',')

                # 5 - Nro. certificado propio
                # opcional y el que nos pasaron no tenia
                content += '                '

                # segun interpretamos de los datos que nos pasaron 6, 7, 8 y 11
                # son del comprobante original
                #or_inv = line.move_id._found_related_invoice()
                or_inv = line.move_id.reversed_entry_id
                if not or_inv:
                    raise ValidationError(_(
                        'No pudimos encontrar el comprobante original para %s '
                        '(id %s). Verifique que en la nota de crédito "%s", el'
                        ' campo origen es el número de la factura original'
                    ) % (
                        line.move_id.display_name,
                        line.move_id.id,
                        line.move_id.display_name))

                # 6 - Tipo de comprobante origen de la retención
                # por ahora solo tenemos facturas implementadas
                content += '01'

                # 7 - Letra del Comprobante
                if payment:
                    content += ' '
                else:
                    content += or_inv.l10n_latam_document_type_id.l10n_ar_letter

                # 8 - Nro de comprobante (original)
                content += '%016d' % int(
                    re.sub('[^0-9]', '', or_inv.l10n_latam_document_number or ''))

                # 9 - Nro de documento del Retenido
                content += str(partner._get_id_number_sanitize())

                # 10 - Código de norma
                # por ahora solo padron regimenes generales
                content += '029'

                # 11 - Fecha de retención/percepción
                content += fields.Date.from_string(
                    or_inv.invoice_date).strftime('%d/%m/%Y')

                # 12 - Ret/percep a deducir

                # si la línea tiene moneda diferente de la moneda de la compañía queremos que la ret/perc
                # se calcule aplicando la alícuota sobre la base imponible en la moneda de la compañía
                if line.currency_id and line.currency_id != line.company_id.currency_id:
                    ret_perc_applied = float_round((taxable_amount*alicuot/100), precision_digits=2)
                content += format_amount((line.balance if not ret_perc_applied else ret_perc_applied), 16, 2, ',')

                # 13 - Alícuota
                content += format_amount(alicuot, 5, 2, ',')

                content += '\r\n'

                credito += content
                continue

            # 2 - Código de Norma
            # por ahora solo padron regimenes generales
            content += '029'

            # 3 - Fecha de retención/percepción
            content += fields.Date.from_string(line.date).strftime('%d/%m/%Y')

            # 4 - Tipo de comprobante origen de la retención
            if internal_type == 'invoice':
                content += '01'
            elif internal_type == 'debit_note':
                if es_percepcion:
                    content += '09'
                else:
                    content += '02'
            else:
                # orden de pago
                content += '03'

            # 5 - Letra del Comprobante
            # segun vemos en los archivos de ejemplo solo en percepciones
            if payment:
                content += ' '
            else:
                content += line.l10n_latam_document_type_id.l10n_ar_letter

            # 6 - Nro de comprobante
            content += '%016d' % int(
                re.sub('[^0-9]', '', move.l10n_latam_document_number or ''))

            # 7 - Fecha del comprobante
            content += fields.Date.from_string(move.date).strftime('%d/%m/%Y')

            # obtenemos montos de los comprobantes
            payment_group = line.payment_id.payment_group_id
            if payment_group:
                # solo en comprobantes A, M segun especificacion
                vat_amount = 0.0
                total_amount = float_round(payment_group.payments_amount, precision_digits=2)
                # es lo mismo que payment_group.matched_amount_untaxed
                taxable_amount = float_round(payment.withholdable_base_amount, precision_digits=2)

                # lo sacamos por diferencia
                other_taxes_amount = company_currency.round(
                    total_amount - taxable_amount - vat_amount)
            elif line.move_id.is_invoice():
                amounts = line.move_id._l10n_ar_get_amounts(company_currency=True)
                # segun especificacion el iva solo se reporta para estos
                if line.l10n_latam_document_type_id.l10n_ar_letter in ['A', 'M']:
                    vat_amount = amounts['vat_amount']
                else:
                    vat_amount = 0.0

                total_amount = (1 if line.move_id.is_inbound() else -1) * line.move_id.amount_total_signed

                # por si se olvidaron de poner agip en una linea de factura
                # la base la sacamos desde las lineas de impuesto
                # taxable_amount = line.move_id.cc_amount_untaxed
                taxable_amount = line.tax_base_amount

                # tambien lo sacamos por diferencia para no tener error (por el
                # calculo trucado de taxable_amount por ejemplo) y
                # ademas porque el iva solo se reporta si es factura A, M
                other_taxes_amount = company_currency.round(
                    total_amount - taxable_amount - vat_amount)
                # other_taxes_amount = line.move_id.cc_other_taxes_amount
            else:
                raise ValidationError(_('El impuesto no está asociado'))

            # 8 - Monto del comprobante
            content += format_amount(total_amount, 16, 2, ',')

            # 9 - Nro de certificado propio
            content += (payment.withholding_number or '').rjust(16, ' ')

            # 10 - Tipo de documento del Retenido
            # vat
            if partner.l10n_latam_identification_type_id.name not in ['CUIT', 'CUIL', 'CDI']:
                raise ValidationError(_(
                    'EL el partner "%s" (id %s), el tipo de identificación '
                    'debe ser una de siguientes: CUIT, CUIL, CDI.' % (partner.id, partner.name)))
            doc_type_mapping = {'CUIT': '3', 'CUIL': '2', 'CDI': '1'}
            content += doc_type_mapping[partner.l10n_latam_identification_type_id.name]

            # 11 - Nro de documento del Retenido
            content += str(partner._get_id_number_sanitize())

            # 12 - Situación IB del Retenido
            # 1: Local 2: Convenio Multilateral
            # 4: No inscripto 5: Reg.Simplificado
            if not partner.l10n_ar_gross_income_type:
                #raise ValidationError(_(
                    #'Debe setear el tipo de inscripción de IIBB del partner '
                    #'"%s" (id: %s)') % (partner.name, partner.id))
                partner.l10n_ar_gross_income_type = 'multilateral'

            # ahora se reportaria para cualquier inscripto el numero de cuit
            gross_income_mapping = {
                'local': '5', 'multilateral': '2', 'exempt': '4'}
            content += gross_income_mapping[partner.l10n_ar_gross_income_type]

            # 13 - Nro Inscripción IB del Retenido
            if partner.l10n_ar_gross_income_type == 'exempt':
                content += '00000000000'
            else:
                content += partner.ensure_vat()

            # 14 - Situación frente al IVA del Retenido
            # 1 - Responsable Inscripto
            # 3 - Exento
            # 4 - Monotributo
            res_iva = partner.l10n_ar_afip_responsibility_type_id
            if res_iva.code in ['1', '1FM']:
                # RI
                content += '1'
            elif res_iva.code == '4':
                # EXENTO
                content += '3'
            elif res_iva.code == '6':
                # MONOT
                content += '4'
            else:
                raise ValidationError(_(
                    'La responsabilidad frente a IVA "%s" no está soportada '
                    'para ret/perc AGIP (partner %s)') % (res_iva.name,partner.name) )

            # 15 - Razón Social del Retenido
            content += '{:30.30}'.format(partner.name)

            # 16 - Importe otros conceptos
            content += format_amount(other_taxes_amount, 16, 2, ',')

            # 17 - Importe IVA
            content += format_amount(vat_amount, 16, 2, ',')

            # 18 - Monto Sujeto a Retención/ Percepción
            content += format_amount(taxable_amount, 16, 2, ',')

            # 19 - Alícuota
            content += format_amount(alicuot, 5, 2, ',')

            # 20 - Retención/Percepción Practicada

            # si la línea tiene moneda diferente de la moneda de la compañía queremos que la ret/perc
            # se calcule aplicando la alícuota sobre la base imponible en la moneda de la compañía
            if line.currency_id and line.currency_id != line.company_id.currency_id:
                ret_perc_applied = float_round((taxable_amount*alicuot/100), precision_digits=2)
            content += format_amount((-line.balance if not ret_perc_applied else ret_perc_applied), 16, 2, ',')

            # 21 - Monto Total Retenido/Percibido
            content += format_amount((-line.balance if not ret_perc_applied else ret_perc_applied), 16, 2, ',')

            content += '\r\n'

            ret_perc += content

        _logger.info(move_lines.ids)
        self.write({'export_arciba_data':ret_perc,'export_arciba_data_credito':credito,'move_lines_ids_txt' : move_lines.ids})
        return [{
                'txt_filename': 'Perc/Ret IIBB AGIP Aplicadas.txt',
                'txt_content': ret_perc,
                }, {
                'txt_filename': 'NC Perc/Ret IIBB AGIP Aplicadas.txt',
                'txt_content': credito,
                }]



    def set_done(self):
        self.create_table_ret()
        self.state = 'done'

    def set_draft(self):
        self.env['account.export.tax'].sudo().search([('export_id','=',self.id)]).unlink()
        self.state = 'draft'

