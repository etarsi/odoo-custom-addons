from odoo import models, api, fields, _


class AccountMoveReversalInherit(models.Model):
    _inherit = 'account.vat.ledger'


    total_vat_21 = fields.Float('Total IVA 21%', compute="_compute_total_vat_21", store=True)
    total_grav_21 = fields.Float('Total Gravado 21%', compute="_compute_total_grav_21", store=True)
    total_other_taxes = fields.Float('Total Impuestos Otros', compute="_compute_total_other_taxes", store=True)
    total_iibb_taxes = fields.Float('Total IIBB', compute="_compute_total_iibb_taxes", store=True)
    total_final = fields.Float('Total Impuestos', compute="_compute_total_final", store=True)
    total_not_taxed = fields.Float('Total No Gravado', compute="_compute_total_not_taxed", store=True)


    # COMPUTED
    @api.depends('invoice_ids')
    def _compute_total_not_taxed(self):
        for record in self:
            record.total_not_taxed = sum(record.invoice_ids.mapped('not_taxed'))

    @api.depends('invoice_ids')
    def _compute_total_vat_21(self):
        for record in self:
            record.total_vat_21 = sum(record.invoice_ids.mapped('vat_21'))

    
    @api.depends('invoice_ids')
    def _compute_total_grav_21(self):
        for record in self:
            record.total_grav_21 = sum(record.invoice_ids.mapped('base_21'))

    
    @api.depends('invoice_ids')
    def _compute_total_other_taxes(self):
        for record in self:
            record.total_other_taxes = sum(record.invoice_ids.mapped('other_taxes'))

    @api.depends('invoice_ids')
    def _compute_total_iibb_taxes(self):
        for record in self:
            record.total_iibb_taxes = sum(record.invoice_ids.mapped('iibb_taxes'))


    @api.depends('invoice_ids')
    def _compute_total_final(self):
        for record in self:
            record.total_final = sum(record.invoice_ids.mapped('total'))