# -*- coding: utf-8 -*-
from odoo import fields, models


class PriceRule(models.Model):
    _inherit = "delivery.price.rule"

    list_price = fields.Float(digits=(12, 3))
