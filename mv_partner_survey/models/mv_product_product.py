# -*- coding: utf-8 -*-
from odoo import _, fields, models, tools

PRODUCT_TYPEs = [("size_lop", "Size Lốp"), ("lubricant", "Dầu nhớt")]


class MvSProductProduct(models.Model):
    _name = "mv.product.product"
    _description = _("Product Variant")

    @tools.ormcache()
    def _get_default_uom_id(self):
        # Deletion forbidden (at least through unlink)
        return self.env.ref("uom.product_uom_unit")

    active = fields.Boolean("Active", default=True)
    mv_product_attribute_id = fields.Many2one("mv.product.attribute", "Attribute")
    brand_id = fields.Many2one("mv.brand", "Brand")
    quantity_per_month = fields.Integer("Quantity per Month")
    uom_id = fields.Many2one(
        "uom.uom", "Unit of Measure", default=_get_default_uom_id, required=True
    )
    uom_name = fields.Char("Unit of Measure Name", related="uom_id.name", readonly=True)
    product_type = fields.Selection(
        PRODUCT_TYPEs, default="size_lop", string="Loại sản phẩm", required=True
    )
