# -*- coding: utf-8 -*-
from odoo import _, api, fields, models, tools

PRODUCT_TYPEs = [("size_lop", "Size Lốp"), ("lubricant", "Dầu nhớt")]


class MvSProductProduct(models.Model):
    _name = "mv.product.product"
    _description = _("Product Variant")

    @tools.ormcache()
    def _get_default_uom_id(self):
        # Deletion forbidden (at least through unlink)
        return self.env.ref("uom.product_uom_unit")

    active = fields.Boolean("Active", default=True)
    name = fields.Char(compute="_compute_name", store=True, readonly=False)
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

    @api.onchange("brand_id")
    def _onchange_brand_id(self):
        if self.brand_id:
            self.product_type = self.brand_id.type

    @api.depends("mv_product_attribute_id", "brand_id")
    def _compute_name(self):
        for product in self:
            if product.mv_product_attribute_id and product.brand_id:
                product.name = "%s %s (%s)" % (
                    product.brand_id.name,
                    product.mv_product_attribute_id.name,
                    (
                        "Loại: Lốp xe"
                        if product.brand_id.type == "size_lop"
                        else "Loại: Dầu nhớt"
                    ),
                )
            else:
                product.name = "NEW"
