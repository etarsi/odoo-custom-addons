# -*- coding: utf-8 -*-
from xmlrpc import client
import sys
import re
import openpyxl
import csv
from datetime import datetime
import sys
import re
from datetime import datetime
import html2text
"""Reportlab trying a rounded table.
"""
import codecs
import configparser
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
import locale
import re
import sys
import os
import textwrap
#connection = pymongo.MongoClient("mongodb://localhost")
#db = connection.sipac
#global sipac
#sipac = db.sipac
fondogris=colors.Color(.95,.95,.95,1)



url = "https://one.sebigus.com.ar"
dbname = "one"
user = "admin"
pwd = "Sebigus123!"
common = client.ServerProxy('{}/xmlrpc/2/common'.format(url))
res = common.version()
uid = common.authenticate(dbname, user, pwd, {})
models = client.ServerProxy('{}/xmlrpc/2/object'.format(url))
# Busco liquidaciones por periodo
def main(proceso):
    global sipac
    #sipac   = eval('db.%s%s' % (sipac1,proceso))
    papel = A4
    #for cabecera in result['result']:
    print(' Buscando liquida#ciones')
    sal_directorio = '/opt/odoo15/odoo-custom-addons/l10n_ar_report_stock'
    cmd = []
    for rem in models.execute_kw(dbname,uid,pwd,'stock.picking','search_read',[[['id','=',proceso]]]):
        print(rem)
        sal_archivo=re.sub(' ','_',re.sub('/','_',rem['name']))
        sal_archivo='%s.pdf' % sal_archivo
        sal_archivo='REM%s.pdf' % proceso
        #partner = models.execute_kw(dbname,uid,pwd,'res.partner','search_read',[[['id','=',rem['partner_id'][0] ]]],{'fields': ['name','street','city','vat','l10n_ar_afip_responsability_type_id','country']})
        p = models.execute_kw(dbname,uid,pwd,'res.partner','search_read',[[['id','=',rem['partner_id'][0] ]]],{'fields': ['name','street','city','vat','l10n_ar_afip_responsibility_type_id','country_id']})
        partner= p[0]
        print(partner)
        # Preparo recibos separados
        doc = canvas.Canvas('%s/%s' % (sal_directorio,sal_archivo),pagesize=papel)
        def cabecera():
            font_name = 'Helvetica'
            font_size = 12
            doc.setFont(font_name, font_size)
            doc.drawString(15*cm,25*cm,datetime.strptime(rem['date_done'],'%Y-%m-%d %H:%M:%S').strftime('%d-%m-%Y') )
            # Cabecera remito
            doc.drawString(5*cm,22*cm,partner['name'])
            doc.drawString(5*cm,21.5*cm,partner['street'])
            doc.drawString(5*cm,21*cm,partner['city'])
            doc.drawString(15*cm,22*cm,partner['vat'])
            doc.drawString(15*cm,21.5*cm,partner['l10n_ar_afip_responsibility_type_id'][1])
            font_name = 'Helvetica'
            font_size = 10
            doc.setFont(font_name, font_size)
            doc.drawString(5*cm,20.0*cm,"Origen : %s " % rem['origin'])
            doc.drawString(8*cm,20.0*cm,"%s " % rem['codigo_wms'])
            # Busco carrier
            if rem['carrier_id'][1]:
                doc.drawString(15*cm,20.0*cm,"%s " % rem['carrier_id'][1])
        def pie():
            font_name = 'Helvetica'
            font_size = 12
            doc.setFont(font_name, font_size)
            # Cabecera remito
            doc.drawString(5*cm,5*cm,'Numero de Paquetes: %s' %  rem['number_of_packages'])
            doc.drawString(5*cm,4*cm,'Cantidd de Bultos:  %.2f' %  rem['packaging_qty'])
            doc.drawString(5*cm,3*cm,'Valor:              %s' %  rem['declared_value'])
        cabecera()
        pos = 17
        pos_l = 0
        #for l in rem['move_line_ids']:
        # Lotes
        lotes={}
        for ml in rem['move_line_ids_without_package']:
            for lote in  models.execute_kw(dbname,uid,pwd,'stock.move.line','search_read',[[['id','=',ml]]]):
                ll=  models.execute_kw(dbname,uid,pwd,'stock.production.lot','search_read',[[['id','=',lote['lot_id'][0]]]])
                lotes[lote['product_id'][0]] = ll[0]['dispatch_number']
        for l in rem['move_ids_without_package']:
            font_name = 'Courier'
            font_size = 6
            doc.setFont(font_name, font_size)
            pos_l=pos_l +1
            move_line = models.execute_kw(dbname,uid,pwd,'stock.move','search_read',[[['id','=',l]]])
            ml = move_line[0]
            pos = pos - 0.5
            desc = html2text.html2text(re.sub('\n','',ml['product_id'][1]))
            desc = desc.strip()
            doc.drawString(1*cm,pos*cm,'%.2f' % ml['product_packaging_qty'])
            desc = re.sub('\n','',desc)
            doc.drawString(3*cm,pos*cm,desc)
            doc.drawString(15*cm,pos*cm,'%s' % lotes[ml['product_id'][0]])
            doc.drawString(19*cm,pos*cm,'%d' % ml['quantity_done'])
            if pos_l == 15:
                doc.showPage()
                pos = 17
                pos_l = 0
            cabecera()

        pie()
        doc.showPage()
        doc.save()
main(sys.argv[1])
