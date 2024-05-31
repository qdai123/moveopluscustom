# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MvDiscountPolicyPartner(models.Model):
    _name = _description = "mv.discount.partner"

    date = fields.Date("Date Effective", default=fields.Date.today)
    level = fields.Integer("Level", default=0)
    min_debt = fields.Integer("Min Debt", default=0)
    max_debt = fields.Integer("Max Debt", default=0)
    number_debt = fields.Float("Ratio Debt", default=0)
    # RELATION Fields
    parent_id = fields.Many2one(
        "mv.discount",
        "Chính sách chiết khấu",
        domain=[("active", "=", True)],
        help="Parent Model: mv.discount",
    )
    warranty_discount_policy_id = fields.Many2one(
        "mv.warranty.discount.policy",
        "Chính sách chiết khấu bảo hành",
        domain=[("active", "=", True)],
        help="Parent Model: mv.warranty.discount.policy",
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Khách hàng / Đại lý",
        domain=[("is_agency", "=", True)],
        help="Parent Model: res.partner",
    )
    partner_agency = fields.Boolean()
    partner_white_agency = fields.Boolean()
