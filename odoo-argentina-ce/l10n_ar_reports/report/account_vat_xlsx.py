# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models
import logging

_logger = logging.getLogger(__name__)


class AccountVatLedgerXlsx(models.AbstractModel):
    _name = "report.account_vat_ledger_xlsx"
    _description = "report vat ledger in xlsx"
    _inherit = "report.report_xlsx.abstract"

    def generate_xlsx_report(self, workbook, data, vat_ledger):
        if vat_ledger.invoice_ids:
            report_name = "IVA Ventas/Compras"
            sheet = workbook.add_worksheet(report_name[:31])
            money_format = workbook.add_format({"num_format": "$#,##0"})
            bold = workbook.add_format({"bold": True})
            sheet.write(1, 0, vat_ledger.display_name, bold)
            titles = [None] * 50
            titles[0] = "Fecha"
            titles[1] = "Cliente/Proveedor"
            titles[2] = "CUIT"
            titles[3] = "Tipo Comprobante"
            titles[4] = "Responsabilidad AFIP"
            titles[5] = "N° Comprobante"
            titles[6] = "NO gravado/Excento"
            titles[7] = "Monto gravado 2,5%"
            titles[8] = "IVA 2,5%"
            titles[9] = "Monto gravado 5%"
            titles[10] = "IVA 5%"
            titles[11] = "Monto gravado 10,5%"
            titles[12] = "IVA 10.5%"
            titles[13] = "Monto gravado 21%"
            titles[14] = "IVA 21%"
            titles[15] = "Monto gravado 27%"
            titles[16] = "IVA 27%"
            titles[17] = "Percepciones"
            titles[18] = "IIBB"
            titles[19] = "CABA"
            titles[20] = "ARBA"
            titles[21] = "Catamarca"
            titles[22] = "Córdoba"
            titles[23] = "Corrientes"
            titles[24] = "Entre Ríos"
            titles[25] = "Jujuy"
            titles[26] = "Mendoza"
            titles[27] = "La Rioja"
            titles[28] = "Salta"
            titles[29] = "San Juan"
            titles[30] = "San Luis"
            titles[31] = "Santa Fe"
            titles[32] = "Santiago del Estero"
            titles[33] = "Tucumán"
            titles[34] = "Chaco"
            titles[35] = "Chubut"
            titles[36] = "Formosa"
            titles[37] = "Misiones"
            titles[38] = "Neuquén"
            titles[39] = "La Pampa"
            titles[40] = "Río Negro"
            titles[41] = "Santa Cruz"
            titles[42] = "Tierra del Fuego"
            titles[43] = "Otros"
            titles[44] = "Total"

            for i, title in enumerate(titles):
                sheet.write(3, i, title, bold)
            row = 4
            index = 0
            sheet.set_column("A:F", 30)
            for i, obj in enumerate(vat_ledger.invoice_ids):
                sheet.write(row + index, 0, obj.invoice_date.strftime("%Y-%m-%d"))
                sheet.write(row + index, 1, obj.partner_name)
                sheet.write(row + index, 2, obj.cuit)
                sheet.write(row + index, 3, obj.document_type_id.display_name)
                sheet.write(row + index, 4, obj.afip_responsibility_type_name)
                sheet.write(row + index, 5, obj.move_name)
                sheet.write(row + index, 6, obj.not_taxed, money_format)
                sheet.write(row + index, 7, obj.base_25, money_format)
                sheet.write(row + index, 8, obj.vat_25, money_format)
                sheet.write(row + index, 9, obj.base_5, money_format)
                sheet.write(row + index, 10, obj.vat_5, money_format)
                sheet.write(row + index, 11, obj.base_10, money_format)
                sheet.write(row + index, 12, obj.vat_10, money_format)
                sheet.write(row + index, 13, obj.base_21, money_format)
                sheet.write(row + index, 14, obj.vat_21, money_format)
                sheet.write(row + index, 15, obj.base_27, money_format)
                sheet.write(row + index, 16, obj.vat_27, money_format)
                sheet.write(row + index, 17, obj.vat_per, money_format)
                sheet.write(row + index, 18, obj.iibb_taxes, money_format)
                sheet.write(row + index, 19, obj.iibb_caba, money_format)
                sheet.write(row + index, 20, obj.iibb_arba, money_format)
                sheet.write(row + index, 21, obj.iibb_catamarca, money_format)
                sheet.write(row + index, 22, obj.iibb_cordoba, money_format)
                sheet.write(row + index, 23, obj.iibb_corrientes, money_format)
                sheet.write(row + index, 24, obj.iibb_entrerios, money_format)
                sheet.write(row + index, 25, obj.iibb_jujuy, money_format)
                sheet.write(row + index, 26, obj.iibb_mendoza, money_format)
                sheet.write(row + index, 27, obj.iibb_larioja, money_format)
                sheet.write(row + index, 28, obj.iibb_salta, money_format)
                sheet.write(row + index, 29, obj.iibb_sanjuan, money_format)
                sheet.write(row + index, 30, obj.iibb_sanluis, money_format)
                sheet.write(row + index, 31, obj.iibb_santafe, money_format)
                sheet.write(row + index, 32, obj.iibb_santiagodelestero, money_format)
                sheet.write(row + index, 33, obj.iibb_tucuman, money_format)
                sheet.write(row + index, 34, obj.iibb_chaco, money_format)
                sheet.write(row + index, 35, obj.iibb_chubut, money_format)
                sheet.write(row + index, 36, obj.iibb_formosa, money_format)
                sheet.write(row + index, 37, obj.iibb_misiones, money_format)
                sheet.write(row + index, 38, obj.iibb_neuquen, money_format)
                sheet.write(row + index, 39, obj.iibb_lapampa, money_format)
                sheet.write(row + index, 40, obj.iibb_rionegro, money_format)
                sheet.write(row + index, 41, obj.iibb_santacruz, money_format)
                sheet.write(row + index, 42, obj.iibb_tierradelfuego, money_format)
                sheet.write(row + index, 43, obj.other_taxes, money_format)
                sheet.write(row + index, 44, obj.total, money_format)

                index += 1
