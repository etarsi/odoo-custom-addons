
from odoo import fields, models, tools, api
from odoo.exceptions import AccessError
import logging
_logger = logging.getLogger(__name__)

class ResPartnerInherit(models.Model):
    _inherit = 'res.partner'


    def action_print_debt_report(self):
        self.ensure_one()
        
        partner_id = self.id
        company_ids = [1, 2, 3, 4] # IDs de compañías a considerar
        
        # refrescamos la tabla SQL SOLO para ese cliente y esas compañías
        self.env['report.debt.composition.client.company'].action_refresh_sql(
            partner_id=partner_id,
            company_ids=company_ids,
        )
        data=[]
        lines = self.env['report.debt.composition.client.company'].search([('partner', '=', partner_id), ('company_id', 'in', company_ids)])
        if lines:
            #modificar la fecha por el formato d/m/Y
            for line in lines:
                if line.date:
                    line.date = line.date.strftime('%d/%m/%Y')
            return self.env.ref(
                'debt_composition.report_debt_composition_client_company_pdf'
            ).report_action(lines)
        else:
            raise AccessError("No hay datos para mostrar en el reporte de composición de deuda.")