# -*- coding: utf-8 -*-
from odoo import fields, models


class LoyaltyReward(models.Model):
    _inherit = "loyalty.reward"

    apply_only_for_price_total_before_discount = fields.Boolean(
        string="Apply before Discount Amount",
        default=False,
        help="Áp dụng theo chính sách của MO+, các chương trình đặc biệt.",
    )
