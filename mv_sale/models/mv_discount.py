# -*- coding: utf-8 -*-

from odoo import models, api, fields


class MvDiscount(models.Model):
    _name = 'mv.discount'

    name = fields.Char(string="Chính sách chiết khấu", required=False)
    line_ids = fields.One2many("mv.discount.line", "parent_id")
    partner_ids = fields.One2many("mv.discount.partner", "parent_id")
