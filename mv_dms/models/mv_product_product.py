# -*- coding: utf-8 -*-
from odoo import _, api, fields, models, tools

PRODUCT_TYPEs = [
    ("size_lop", "Size Lốp"),
    ("lubricant", "Dầu nhớt"),
    ("battery", "Ắc quy"),
]


class MvProductProduct(models.Model):
    _name = "mv.product.product"
    _description = _("Product Variant")
    _order = "product_code, name, id"

    @tools.ormcache()
    def _get_default_uom_id(self):
        # Deletion forbidden (at least through unlink)
        return self.env.ref("uom.product_uom_unit")

    active = fields.Boolean(
        "Active",
        default=True,
        help="If unchecked, it will allow you to hide the product without removing it.",
    )
    name = fields.Char(
        "Tên sản phẩm",
        compute="_compute_name",
        store=True,
        readonly=False,
        index="trigram",
    )
    partner_survey_ref = fields.Char(
        "Mã khảo sát đối tác",
        compute="_compute_partner_survey_ref",
    )
    product_type = fields.Selection(
        PRODUCT_TYPEs,
        "Loại sản phẩm",
        default="size_lop",
        required=True,
    )
    product_code = fields.Char("Mã sản phẩm", index=True)
    product_attribute_id = fields.Many2one("mv.product.attribute", "Thuộc tính")
    brand_id = fields.Many2one("mv.brand", "Hãng/Thương hiệu")
    quantity_per_month = fields.Integer("Số lượng mỗi tháng", default=0)
    uom_id = fields.Many2one("uom.uom", default=_get_default_uom_id, required=True)
    uom_name = fields.Char("Đơn vị", related="uom_id.name", readonly=True)

    _sql_constraints = [
        (
            "name_product_attribute_brand_unique",
            "UNIQUE(name, product_attribute_id, brand_id)",
            "The name of the product must be unique!",
        )
    ]

    @api.onchange("brand_id")
    def _onchange_brand_id(self):
        if self.brand_id:
            self.product_type = self.brand_id.type

    @api.depends("product_attribute_id", "brand_id")
    def _compute_name(self):
        for product in self:
            if product.product_attribute_id and product.brand_id:
                product.name = "%s %s (%s)" % (
                    product.brand_id.name,
                    product.product_attribute_id.name,
                    (
                        "Loại: Lốp xe"
                        if product.brand_id.type == "size_lop"
                        else "Loại: Dầu nhớt"
                    ),
                )

    @api.depends_context("partner_survey_ref")
    def _compute_partner_survey_ref(self):
        for product in self:
            product.partner_survey_ref = self.env.context.get("partner_survey_ref")
