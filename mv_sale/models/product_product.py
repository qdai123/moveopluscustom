# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductAttributeCustomValue(models.Model):
    _inherit = "product.attribute.custom.value"

    mv_discount_policy_product_level_id = fields.Many2one(
        "mv.discount.policy.product.level.line",
        string="Policy Product Level Line",
        ondelete="cascade",
    )

    _sql_constraints = [
        (
            "mv_discount_policy_product_level_line_custom_value_unique",
            "unique(custom_product_template_attribute_value_id, mv_discount_policy_product_level_id)",
            "Only one Custom Value is allowed per Attribute Value per Policy Product Level Line.",
        )
    ]
