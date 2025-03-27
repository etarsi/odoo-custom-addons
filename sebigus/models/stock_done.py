from odoo import tools, models, fields, api, _

class StockMove(models.Model):
    _inherit = "stock.move"

    def action_done(self):
        for rec in self:
            self._action_done()
        return True

class StockScrap(models.Model):
    _inherit = "stock.scrap"

    def action_done(self):
        for rec in self:
            self.action_validate()
        return True
