from odoo import tools, models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from collections import defaultdict
import base64
import logging
import uuid
import requests
from requests.structures import CaseInsensitiveDict
import os
_logger = logging.getLogger(__name__)

class RemitoReporte(models.Model):
    _inherit = "stock.picking"

    def genero_remito(self):
        import html2text
        from datetime import datetime
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate
        from reportlab.platypus import Table
        from reportlab.platypus import TableStyle
        from reportlab.platypus import Paragraph, Spacer, Indenter
        from reportlab.pdfbase.pdfmetrics import registerFont
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import A4, landscape, A5,A6
        from reportlab.lib import colors
        from reportlab.lib.units import cm,mm
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.graphics.barcode.common import I2of5
        from reportlab.graphics.barcode import code39
        import re
        papel = A4
        sal_directorio = '/opt/odoo15/odoo-custom-addons/sebigus-varios/reporte-remito/static/'
        sal_archivo='REM%s_%s.pdf' % (self.id,uuid.uuid4())
        doc = canvas.Canvas('%s/%s' % (sal_directorio,sal_archivo),pagesize=papel)
        pos_ini = -0.5 * cm
        if self.company_id.id != 4:
            pos_ini = 0.7 * cm
        if self.company_id.id == 3:
            pos_ini = 1 * cm
        def verificar():
            null = None
            if self.codigo_wms:
                cod_pedido = self.codigo_wms
                url = self.env['ir.config_parameter'].sudo().get_param('digipwms.url')
                headers = CaseInsensitiveDict()
                headers["X-API-KEY"] = self.env['ir.config_parameter'].sudo().get_param('digipwms.key')
                respGet = requests.get('%s/v1/Pedidos/%s/Detalle' % (url,cod_pedido), headers=headers)
                _logger.info(respGet)
                if respGet.status_code in [200,201] and respGet.content.strip() != b'null':
                    result = eval(respGet.content)
                    pickings = self.env['stock.picking'].sudo().search([('codigo_wms','=',cod_pedido),('state','not in',['draft','cancel'])])
                    # Traigo la cantidad de bultos pickiados en digip
                    # Marco las cantidades que traingo desde digip
                    product_dict = defaultdict(float)
                    for picking in pickings:
                        picking.sudo().write({'codigo_wms':cod_pedido})
                        for move in picking.move_ids_without_package:
                            # Access product_id and product_uom_qty
                            product_code = move.product_id.default_code
                            quantity = move.quantity_done
                            # Accumulate quantities by product_code in the dictionary
                            product_dict[product_code] += quantity
                    for picking in pickings:
                        for det in picking.move_ids_without_package:
                            # Busco codigo en result
                            if det.quantity_done > 0:
                                for r in result:
                                    if r['CodigoArticulo'] == det.product_id.default_code:
                                         ratio =  det.quantity_done / product_dict[det.product_id.default_code] 
                                         unidades = round(ratio*r['UnidadesSatisfecha'],0)
                                         _logger.info('DETALLE %s %s %s %s %s %s' % (det,det.quantity_done,unidades,r['UnidadesSatisfecha'],r['Unidades'],ratio))
                                         if det.quantity_done  != unidades:
                                             raise UserError('Las cantidades remitidas no coinciden con el picking')

        def cabecera():
            font_name = 'Helvetica'
            font_size = 12
            doc.setFont(font_name, font_size)
            doc.drawString(15*cm,25*cm,self.date_done.strftime('%d-%m-%Y') )
            # Cabecera remito
            if self.partner_id.parent_id:
                partner = self.partner_id.parent_id
            else:
                partner = self.partner_id
            doc.drawString(3*cm,22*cm+pos_ini,partner.name)
            doc.drawString(3*cm,21.5*cm+pos_ini,self.partner_id.street)
            doc.drawString(3*cm,21*cm+pos_ini,self.partner_id.city)
            doc.drawString(15*cm,22*cm+pos_ini,'%s'% partner.vat)
            doc.drawString(15*cm,21.5*cm+pos_ini,'%s'% partner.l10n_ar_afip_responsibility_type_id.name)
            font_name = 'Helvetica'
            font_size = 10
            doc.setFont(font_name, font_size)
            doc.drawString(3*cm,20.0*cm+pos_ini,"Origen:")
            doc.drawString(4.5*cm,20.0*cm+pos_ini,"%s" % self.origin)
            doc.drawString(8*cm,20.0*cm+pos_ini,"%s " % self.codigo_wms)
            doc.drawString(4.5*cm,19.5*cm+pos_ini,"%s " % self.name[:25])
            # Busco carrier
            if not self.carrier_id:
                if self.partner_id.property_delivery_carrier_id:
                    self.write({'carrier_id':self.partner_id.property_delivery_carrier_id})
            if self.carrier_id:
                doc.drawString(10*cm,20.0*cm+pos_ini,"%s " % self.carrier_id.name )
                doc.drawString(10*cm,19.5*cm+pos_ini,"%s " % (self.carrier_id.partner_id.name) )
        def pie():
            font_name = 'Helvetica'
            font_size = 12
            doc.setFont(font_name, font_size)
            # Cabecera remito
            doc.drawString(2*cm,4.0*cm+pos_ini,'Cantidad de Bultos:')
            doc.drawString(6.5 * cm,4.0*cm+pos_ini,' %s' %  self.number_of_packages)
            doc.drawString(8.5*cm,4.0*cm+pos_ini,'Cantidad UXB:')
            doc.drawString(12*cm,4.0*cm+pos_ini,'%.2f' %  self.packaging_qty)
            doc.drawString(15*cm,4.0*cm+pos_ini,'Valor: $')
            doc.drawString(17*cm,4.0*cm+pos_ini,'%s' %  self.declared_value)
        verificar()
        cabecera()
        pos = 17
        pos_l = 0
        #for l in rem['move_line_ids']:
        # Lotes
        lotes={}
        for l in self.move_ids_without_package:
            if l.quantity_done == 0:
                continue
            font_name = 'Helvetica'
            font_size = 8
            doc.setFont(font_name, font_size)
            pos_l=pos_l +1
            pos = pos - 0.5
            desc = html2text.html2text(re.sub('\n','',l.product_id.display_name))
            if l.description_bom_line:
                desc = html2text.html2text(re.sub('\n','',l.description_bom_line)).split(':')[1]
            desc = desc.strip()
            desc = desc[:70]
            doc.drawString(1*cm,pos*cm+pos_ini,'%.2f' % l.product_packaging_qty)
            desc = re.sub('\n','',desc)
            doc.drawString(3*cm,pos*cm+pos_ini,desc)
            for lot in self.move_line_ids:
                if lot.product_id == l.product_id:
                    dis = '%s' % lot.lot_id.dispatch_number
                    dis = dis[:20]
                    doc.drawString(15*cm,pos*cm+pos_ini,'%s' % dis)
            doc.drawString(19*cm,pos*cm+pos_ini,'%d' % l.quantity_done)
            if pos_l == 25:
                pie()
                doc.showPage()
                pos = 17
                pos_l = 0
            cabecera()

        pie()
        doc.showPage()
        doc.save()
        prt_file = '%s/%s' % (sal_directorio,sal_archivo)
        _logger.info('PRT %s %s' % (prt_file,self.company_id.short_name)) 
        if  self.company_id.short_name:
            os.system('lp -d %s -o fit-to-page  %s' % (self.company_id.short_name,prt_file) )
            os.system('lp -d %s -o fit-to-page  %s' % (self.company_id.short_name,prt_file) )
            os.system('lp -d %s -o fit-to-page  %s' % (self.company_id.short_name,prt_file) )
        else:
            os.system('lp -d %s -o fit-to-page %s' % ('PRT',prt_file) )
            os.system('lp -d %s -o fit-to-page %s' % ('PRT',prt_file) )
            os.system('lp -d %s -o fit-to-page %s' % ('PRT',prt_file) )
            
        return {
                'type': 'ir.actions.act_url',
                'url': 'reporte-remito/static/%s' % sal_archivo,
                'target': 'new',
        }
