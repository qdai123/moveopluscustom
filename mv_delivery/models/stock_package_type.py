# -*- coding: utf-8 -*-
from odoo import fields, models


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    base_volume = fields.Float(string="Volume", help="Volume of the package type")
