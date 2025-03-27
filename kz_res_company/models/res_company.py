from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError

class ResCompany(models.Model):
    _inherit = 'res.company'

    cai = fields.Char('CAI')
    date_cai = fields.Date('Fecha vencimiento CAI')
    mail_cai = fields.Char('Mails aviso CAI', help='Indicar los mails para avisar 48 hs antes del vencimiento del CAI. Si hay más de un mail se deben separar por coma.')
    user_cai = fields.Many2many('res.users', string='Usuarios de mail', help='Indicar los usuarios para enviar el mail')
    template_cai = fields.Many2one('mail.template', 'Plantilla de mail', help='Indicar la plantilla para el mail')

    def add_working_days(self, start_date, num_days):
        current_date = start_date
        while num_days > 0:
            current_date += timedelta(days=1)
            if current_date.weekday() < 5:  # Monday to Friday are considered working days (0 to 4)
                num_days -= 1
        return current_date

    def send_email_template(self):
        email_template = self.template_cai

        today = fields.Date.context_today(self)
        target_date = self.add_working_days(today, 5)  # 5 días hábiles antes del vencimiento

        if self.date_cai and self.date_cai <= target_date:
            user_ids = self.user_cai

            for user in user_ids:
                try:
                    email_template.send_mail(self.id, force_send=True, email_values={'recipient_ids': [(4, user.partner_id.id)]})
                except Exception as e:
                    raise UserError(_("Error sending email: %s") % str(e))

    @api.model
    def send_email_template_cron_job(self):
        companies = self.search([])

        for company in companies:
            company.send_email_template()


class SendEmailCron(models.Model):
    _name = 'res.company.send_email_cron'
    _description = 'Send Email CAI Cron'

    @api.model
    def send_email_cron_job(self):
        companies = self.env['res.company'].search([])

        for company in companies:
            company.send_email_template()
