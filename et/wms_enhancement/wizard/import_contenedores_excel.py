# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import math
from datetime import timedelta

class ImportContenedoresExcel(models.TransientModel):
    _name = 'import.contenedores.excel'
    _description = 'Wizard: Importar Contenedores desde Excel'

    file = fields.Binary(string='Archivo Excel', required=True)
    nro_despacho = fields.Char(string='Número de Despacho', required=True)
    fecha_llegada = fields.Date(string='ETA')
    
    
    
    def import_data(self):
        return True