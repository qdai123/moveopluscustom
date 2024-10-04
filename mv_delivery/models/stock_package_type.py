# -*- coding: utf-8 -*-
from odoo import fields, models


class PackageType(models.Model):
    _inherit = "stock.package.type"

    base_volume = fields.Float(string="Volume", help="Volume of the package type")
