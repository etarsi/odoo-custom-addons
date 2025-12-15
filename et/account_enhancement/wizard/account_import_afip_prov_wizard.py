# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import RedirectWarning, ValidationError
import math
from datetime import timedelta



class AccountImportAfipProvWizard(models.TransientModel):
    _name = 'account.import.afip.prov.wizard'
    _description = 'Wizard: Importar Facturas AFIP Proveedor'


    file = fields.Binary('Archivo Excel', required=True)
    filename = fields.Char('Nombre de Archivo')
    
    
    def action_import_afip_prov(self):
        self.ensure_one()
        if not self.file:
            raise ValidationError(_("Por favor, seleccioná un archivo para importar."))
        
        # Lógica de importación aquí
        # Decodificar el archivo, leer datos, crear registros, etc.
        
        return {
            'type': 'ir.actions.act_window_close',
        }
    
    
