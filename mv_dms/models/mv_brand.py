# -*- coding: utf-8 -*-
from odoo import _, fields, models

BRAND_TYPEs = [("size_lop", "Size Lốp"), ("lubricant", "Dầu nhớt")]


class MvBrand(models.Model):
    _name = "mv.brand"
    _description = _("Brand")

    name = fields.Char("Thương hiệu", default="NEW", required=True)
    type = fields.Selection(
        BRAND_TYPEs, default="size_lop", string="Loại", required=True
    )

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "Mỗi một Hãng lốp/Thương hiệu phải là DUY NHẤT!",
        )
    ]
