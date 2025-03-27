from odoo import models, fields, api, _
from datetime import datetime, timedelta
from odoo.exceptions import UserError

class AccountMove(models.Model):
    _inherit = 'account.move'

    def update_taxes(self):
       self.with_context(check_move_validity=False)._recompute_dynamic_lines(recompute_all_taxes=True)
