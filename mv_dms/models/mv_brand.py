# -*- coding: utf-8 -*-
from odoo import _, fields, models

BRAND_TYPEs = [("size_lop", "Size Lốp"), ("lubricant", "Dầu nhớt")]


class MvBrand(models.Model):
    """Brand for Partner Survey"""

    _name = "mv.brand"
    _description = _("Brand")

    name = fields.Char("Thương hiệu", required=True)
    type = fields.Selection(BRAND_TYPEs, "Loại", default="size_lop")

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name)",
            "Tên thương hiệu đã tồn tại, vui lòng chọn tên khác!",
        )
    ]
