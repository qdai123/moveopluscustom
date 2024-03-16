# -*- coding: utf-8 -*-

from odoo import models, api, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    line_ids = fields.One2many("mv.discount.partner", "partner_id")
    discount_id = fields.Many2one("mv.discount", compute="compute_discount_id", store=True, readonly=False)
    amount = fields.Integer("amount", copy=False)
    is_agency = fields.Boolean(string="Agency", copy=False)
    bank_guarantee = fields.Boolean(string="Bank guarantee", copy=False)
    discount_bank_guarantee = fields.Float(string="Bảo lãnh ngân hàng", copy=False)

    @api.depends("line_ids")
    def compute_discount_id(self):
        for record in self:
            record.discount_id = False
            line_ids = record.line_ids.filtered(lambda x: x.parent_id)
            if len(line_ids) > 0:
                record.discount_id = line_ids[0].parent_id.id

    @api.onchange("bank_guarantee")
    def onchange_bank_guarantee(self):
        self.discount_bank_guarantee = 0
