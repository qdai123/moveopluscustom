# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LoyaltyRule(models.Model):
    _inherit = "loyalty.rule"

    maximum_qty = fields.Integer("Maximum Quantity", default=0)

    @api.constrains("maximum_qty")
    def _check_maximum_qty(self):
        for rule in self:
            if rule.maximum_qty != 0 and rule.maximum_qty < rule.minimum_qty:
                raise ValidationError(
                    _("The maximum quantity must be greater than minimum quantity.")
                )
