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


class AccountExportArba(models.Model):
    _name = 'account.export.arba'
    _description = 'account export arba'

    name = fields.Char('Name')
    date_from = fields.Date('Fecha desde')
    date_to = fields.Date('Fecha hasta')
    export_arba_data = fields.Text('Contenidos archivo ARBA')
    export_arba_data_credito = fields.Text('Contenidos archivo ARBA Credito')
    company_id = fields.Many2one('res.company','Compañía')
    state = fields.Selection([('draft','Borrador'),('done','Hecho'),],string='Estado',default='draft',copy=False,readonly=False)
    move_lines_ids_txt = fields.Text('move_ids')
    move_lines_ids = fields.One2many('account.move.line','id','Movimientos',_compute="list_move_lines")
    export_arba_filename = fields.Char('Archivo_ARBA',compute='_compute_files')
    export_arba_file = fields.Binary('Archivo_ARBA',readonly=True)
    export_arba_filename_credito = fields.Char('Archivo_ARBA_Credito',compute='_compute_files')
    export_arba_file_credito = fields.Binary('Archivo_ARBA_Credito',readonly=True)    
    

    @api.depends('export_arba_data','export_arba_data_credito')
    def _compute_files(self):
        self.ensure_one()
        # segun vimos aca la afip espera "ISO-8859-1" en vez de utf-8
        # http://www.planillasutiles.com.ar/2015/08/
        # como-descargar-los-archivos-de.html
        #if self.export_arba_data:
        self.export_arba_filename = 'Perc/Ret IIBB ARBA Aplicadas.txt'
        if self.export_arba_data:
           self.export_arba_file = base64.encodestring(self.export_arba_data.encode('ISO-8859-1'))
        self.export_arba_filename_credito = 'NC Perc/Ret IIBB ARBA Aplicadas.txt'
        if self.export_arba_data_credito:
           self.export_arba_file_credito = base64.encodestring(self.export_arba_data_credito.encode('ISO-8859-1'))
           
    def line_move_lines(self):
        return self.env['account.move.line'].search([('id','in',eval(self.move_lines_ids_txt))])

    # ---------------------------------------------------------
    # HELPERS
    # ---------------------------------------------------------

    def _format_date_arba(self, date_value):
        if not date_value:
            raise ValidationError(_("Falta una fecha requerida para ARBA."))
        return fields.Date.to_date(date_value).strftime('%d/%m/%Y')

    def _format_cuit_arba(self, vat):
        """ARBA layout común: 99-99999999-9"""
        if not vat:
            raise ValidationError(_("Falta CUIT/CUIL."))
        digits = re.sub(r'[^0-9]', '', vat or '')
        if len(digits) != 11:
            raise ValidationError(_("El CUIT '%s' no tiene 11 dígitos.") % (vat,))
        return '%s-%s-%s' % (digits[:2], digits[2:10], digits[10:11])

    def _split_arba_document_number(self, move):
        raw = move.l10n_latam_document_number or ''
        nums = re.findall(r'\d+', raw)

        if len(nums) >= 2:
            sucursal = str(int(nums[-2])).zfill(5)
            emision = str(int(nums[-1])).zfill(8)
            return sucursal, emision

        raise ValidationError(_(
            'No se pudo separar sucursal y emisión del comprobante "%s" (%s).'
        ) % (move.display_name, raw))

    def _get_arba_tipo_comp_y_letra(self, move):
        """
        Devuelve:
        tipo_comp ARBA: F/E/C/H/D/I/R
        letra: A/B/C o ' '
        """
        doc = move.l10n_latam_document_type_id
        if not doc:
            raise ValidationError(_("El asiento %s no tiene tipo de documento.") % move.display_name)

        name = (doc.name or '').upper().strip()
        prefix = (doc.doc_code_prefix or '').upper().strip()
        internal_type = doc.internal_type
        letter = (doc.l10n_ar_letter or ' ').strip() or ' '

        # En la versión base de ARBA común, trabajamos sólo con A/B/C o blanco
        if letter not in ['A', 'B', 'C']:
            # para M, E, I, etc. mejor bloquear hasta definir regla
            raise ValidationError(_(
                'El comprobante "%s" tiene letra "%s" y no está contemplado en la exportación ARBA común.'
            ) % (doc.display_name, letter))

        # FACTURAS
        if internal_type == 'invoice':
            # Factura de crédito electrónica MiPyME
            if 'FCE' in prefix or 'ELECTRONICA' in name:
                return 'E', letter

            # Factura común
            if 'FACTURA' in name:
                return 'F', letter

            # Recibo
            if 'RECIBO' in name:
                return 'R', letter

        # NOTAS DE CREDITO
        elif internal_type == 'credit_note':
            if 'NCE' in prefix or 'ELECTRONICA' in name:
                return 'H', letter
            return 'C', letter

        # NOTAS DE DEBITO
        elif internal_type == 'debit_note':
            if 'NDE' in prefix or 'ELECTRONICA' in name:
                return 'I', letter
            return 'D', letter

        raise ValidationError(_(
            'No se pudo mapear el tipo de documento "%s" al tipo de comprobante ARBA.'
        ) % doc.display_name)        
            

    def _format_amount_arba(self, amount, total_len, decimals=2, signed=False):
        """
        Devuelve importe con separador decimal y largo fijo.
        Ej:
          total_len=14 -> 99999999999.99
          total_len=13 -> 9999999999.99
        Si signed=True y es negativo, el signo ocupa la 1ra posición.
        """
        if amount is None:
            amount = 0.0

        amount = float_round(amount, precision_digits=decimals)
        negative = amount < 0
        abs_amt = abs(amount)

        fmt = f"{{:0{total_len}.{decimals}f}}"
        txt = fmt.format(abs_amt)

        if len(txt) > total_len:
            raise ValidationError(_("El importe %s excede el largo permitido (%s).") % (amount, total_len))

        if negative:
            if not signed:
                raise ValidationError(_("El importe %s no puede ser negativo para este diseño ARBA.") % amount)
            txt = '-' + txt[1:]
        return txt

    def _get_arba_operation_type(self, line):
        """
        ARBA pide:
        A = Alta
        B = Baja
        M = Modificación

        Base simple: todo exportado normal -> A
        """
        return 'A'

    def _get_arba_perception_doc_type(self, move):
        """
        Mapea tipos de comprobante ARBA:
        F=Factura, R=Recibo, C=Nota Crédito, D=Nota Débito,
        V=Nota de Venta, E/H/I electrónicos
        """
        internal_type = move.l10n_latam_document_type_id.internal_type
        doc_name = (move.l10n_latam_document_type_id.name or '').lower()
        doc_code = (move.l10n_latam_document_type_id.code or '').lower()

        is_electronic = 'electr' in doc_name or 'electr' in doc_code

        if internal_type == 'invoice':
            return 'E' if is_electronic else 'F'
        elif internal_type == 'credit_note':
            return 'H' if is_electronic else 'C'
        elif internal_type == 'debit_note':
            return 'I' if is_electronic else 'D'

        # fallback conservador
        return 'F'

    def _get_arba_letter(self, move):
        letter = move.l10n_latam_document_type_id.l10n_ar_letter or ' '
        return letter if letter in ['A', 'B', 'C'] else ' '

    def _get_alicuota_arba(self, tax, partner, date):
        alicuot_line = tax.get_partner_alicuot(partner, date)
        if not alicuot_line:
            raise ValidationError(_(
                'No hay alícuota configurada para el partner "%s" con el impuesto "%s".'
            ) % (partner.display_name, tax.display_name))

        # percepción vs retención
        if tax.type_tax_use in ['sale', 'purchase']:
            return alicuot_line.alicuota_percepcion
        return alicuot_line.alicuota_retencion

    # ---------------------------------------------------------
    # LAYOUTS ARBA
    # ---------------------------------------------------------

    def _build_arba_percepcion_11(self, line):
        """
        1.1 Percepciones (excepto act. 29, 7 quincenal y 17 bancos)
        Posiciones:
        1-13  CUIT
        14-23 Fecha percepción
        24    Tipo comp.
        25    Letra
        26-30 Sucursal
        31-38 Emisión
        39-52 Monto imponible
        53-57 Alícuota
        58-70 Importe percepción
        71    Tipo operación
        """
        move = line.move_id
        partner = line.partner_id
        tax = line.tax_line_id

        if not partner:
            raise ValidationError(_("La línea %s no tiene partner.") % line.display_name)
        if not tax:
            raise ValidationError(_("La línea %s no tiene tax_line_id.") % line.display_name)
        if not move.l10n_latam_document_number:
            raise ValidationError(_("El comprobante %s no tiene número.") % move.display_name)

        cuit = self._format_cuit_arba(partner.vat)
        fecha = self._format_date_arba(line.date)
        tipo_comp, letra = self._get_arba_tipo_comp_y_letra(move)
        sucursal, emision = self._split_arba_document_number(move)
        base_amount = float_round(line.tax_base_amount or 0.0, precision_digits=2)
        alicuota = self._get_alicuota_arba(tax, partner, line.date)

        # Importe practicado
        if line.currency_id and line.currency_id != line.company_id.currency_id:
            importe = float_round(base_amount * alicuota / 100.0, precision_digits=2)
        else:
            importe = float_round(-line.balance, precision_digits=2)

        # Nota de crédito: base e importe negativos
        if move.l10n_latam_document_type_id.internal_type == 'credit_note':
            base_amount = -abs(base_amount)
            importe = -abs(importe)
        else:
            base_amount = abs(base_amount)
            importe = abs(importe)

        tipo_operacion = self._get_arba_operation_type(line)

        content = ''
        content += cuit
        content += fecha
        content += tipo_comp
        content += letra
        content += sucursal
        content += emision
        content += self._format_amount_arba(base_amount, 14, 2, signed=True)   # 14
        content += self._format_amount_arba(alicuota, 5, 2, signed=False)      # 5
        content += self._format_amount_arba(importe, 13, 2, signed=True)       # 13
        content += tipo_operacion

        if len(content) != 71:
            raise ValidationError(_("La línea ARBA Percepción 1.1 quedó con largo %s y debe ser 71.") % len(content))

        return content + '\r\n'

    def _build_arba_retencion_17(self, line):
        """
        1.7 Retenciones (excepto act. 26, 6 bancos y 17 bancos/no bancos)
        Posiciones:
        1-13  CUIT
        14-23 Fecha retención
        24-28 Sucursal
        29-36 Emisión
        37-50 Monto imponible
        51-55 Alícuota
        56-68 Importe retención
        69    Tipo operación
        """
        move = line.move_id
        partner = line.partner_id
        tax = line.tax_line_id
        payment = line.payment_id

        if not partner:
            raise ValidationError(_("La línea %s no tiene partner.") % line.display_name)
        if not tax:
            raise ValidationError(_("La línea %s no tiene tax_line_id.") % line.display_name)

        # Para retenciones normalmente tomamos comprobante del pago/retención
        doc_number = (payment and payment.withholding_number) or move.l10n_latam_document_number
        if not doc_number:
            raise ValidationError(_("La línea %s no tiene número de comprobante/retención.") % line.display_name)

        cuit = self._format_cuit_arba(partner.vat)
        fecha = self._format_date_arba(line.date)
        sucursal, emision = self._split_arba_document_number(move)
        base_amount = float_round(abs(line.tax_base_amount or 0.0), precision_digits=2)
        alicuota = self._get_alicuota_arba(tax, partner, line.date)

        if line.currency_id and line.currency_id != line.company_id.currency_id:
            importe = float_round(base_amount * alicuota / 100.0, precision_digits=2)
        else:
            importe = float_round(abs(line.balance), precision_digits=2)

        tipo_operacion = self._get_arba_operation_type(line)

        content = ''
        content += cuit                                      # 13
        content += fecha                                     # 10
        content += sucursal                                  # 5
        content += emision                                   # 8
        content += self._format_amount_arba(base_amount, 14, 2, signed=False)  # 14
        content += self._format_amount_arba(alicuota, 5, 2, signed=False)      # 5
        content += self._format_amount_arba(importe, 13, 2, signed=False)      # 13
        content += tipo_operacion                            # 1

        if len(content) != 69:
            raise ValidationError(_("La línea ARBA Retención 1.7 quedó con largo %s y debe ser 69.") % len(content))

        return content + '\r\n'

    # ---------------------------------------------------------
    # PROCESO
    # ---------------------------------------------------------

    def compute_arba_data(self):
        self.ensure_one()

        ret_lines_txt = ''
        per_lines_txt = ''
        exported_ids = []

        # Ajustá estas cuentas a tus cuentas reales
        move_lines_per = self.env['account.move.line'].search([
            ('parent_state', '=', 'posted'),
            ('account_id.code', '=', '2.1.3.02.060'),
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ])

        move_lines_ret = self.env['account.move.line'].search([
            ('parent_state', '=', 'posted'),
            ('account_id.code', '=', '2.1.3.02.050'),
            ('company_id', '=', self.company_id.id),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ])

        # PERCEPCIONES -> layout 1.1
        for line in move_lines_per.sorted(lambda l: (l.date, l.id)):
            if not line.partner_id:
                continue
            per_lines_txt += self._build_arba_percepcion_11(line)
            exported_ids.append(line.id)

        # RETENCIONES -> layout 1.7
        for line in move_lines_ret.sorted(lambda l: (l.date, l.id)):
            if not line.partner_id:
                continue
            ret_lines_txt += self._build_arba_retencion_17(line)
            exported_ids.append(line.id)

        self.write({
            'export_arba_data': per_lines_txt,
            'export_arba_data_credito': ret_lines_txt,
            'move_lines_ids_txt': [(6, 0, exported_ids)],
        })

        return [
            {
                'txt_filename': 'ARBA_Retenciones_1_7.txt',
                'txt_content': ret_lines_txt,
            },
            {
                'txt_filename': 'ARBA_Percepciones_1_1.txt',
                'txt_content': per_lines_txt,
            }
        ]



    def set_done(self):
        self.create_table_ret()
        self.state = 'done'

    def set_draft(self):
        self.env['account.export.tax'].sudo().search([('export_id','=',self.id)]).unlink()
        self.state = 'draft'

