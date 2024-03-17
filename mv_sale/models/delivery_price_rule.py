# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class PriceRule(models.Model):
    _inherit = "delivery.price.rule"

    list_price = fields.Float(digits=(12,3))
