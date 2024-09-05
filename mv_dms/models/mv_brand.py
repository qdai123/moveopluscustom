# -*- coding: utf-8 -*-
from odoo import _, fields, models, tools

BRAND_TYPEs = [
    ("size_lop", "Size Lốp"),
    ("lubricant", "Dầu nhớt"),
    ("battery", "Ắc quy"),
]


class MvBrand(models.Model):
    """Brand for Partner Survey"""

    _name = "mv.brand"
    _description = _("Brand")

    @tools.ormcache()
    def _get_default_uom_id(self):
        # Deletion forbidden (at least through unlink)
        return self.env.ref("uom.product_uom_unit")

    name = fields.Char("Thương hiệu", required=True)
    type = fields.Selection(BRAND_TYPEs, "Loại", default="size_lop")
    uom_id = fields.Many2one("uom.uom", default=_get_default_uom_id, required=True)
    uom_name = fields.Char("Đơn vị", related="uom_id.name", readonly=True)
    mv_brand_categ_id = fields.Many2one("mv.brand.category", "Danh mục thương hiệu")

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name)",
            "Tên thương hiệu đã tồn tại, vui lòng chọn tên khác!",
        )
    ]
