# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MvDiscount(models.Model):
    _name = "mv.discount"
    _description = _("Moveo PLus Discount (%)")

    name = fields.Char(
        string="Chính sách chiết khấu"
    )  # TODO: English should be used as default
    line_ids = fields.One2many("mv.discount.line", "parent_id")
    partner_ids = fields.One2many("mv.discount.partner", "parent_id")
