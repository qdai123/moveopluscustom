# -*- coding: utf-8 -*-
import logging
import re

from unidecode import unidecode

from odoo import fields, models

_logger = logging.getLogger(__name__)


def format_attribute_codes(text):
    # Chuyển từ có dấu sang không dấu
    text = unidecode(text)

    # Chuyển thành chữ thường và thay thế khoảng trắng bằng dấu gạch dưới
    text = text.lower().replace(" ", "_")

    # Loại bỏ các dấu ngoặc và dấu hai chấm
    text = text.replace("(", "").replace(")", "").replace(":", "")

    # Loại bỏ các ký tự đặc biệt, chỉ giữ lại chữ cái, số và dấu gạch dưới
    text = re.sub(r"[^a-z0-9_]", "", text)

    return text


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    attribute_code = fields.Char("Code", copy=False)
    warranty_discount_policy_ids = fields.Many2many(
        "mv.warranty.discount.policy",
        "mv_warranty_discount_product_attribute_rel",
        "mv_warranty_discount_policy_id",
        "product_attribute_id",
        string="Chính sách chiết khấu kích hoạt",
        help="Parent Model: mv.warranty.discount.policy",
    )

    _sql_constraints = [
        (
            "attribute_name_code_create_variant_uniq",
            "unique(name, attribute_code, create_variant)",
            "A code with the same name already exists for this property. Please use another code.",
        )
    ]

    def action_generate_attribute_code(self):
        # [!] Remove all attribute_code before generate new one
        self.filtered(lambda r: r.attribute_code).write({"attribute_code": None})

        valid_attr_codes = []
        codes_generated = (
            self.env["product.attribute"].search([]).mapped("attribute_code")
        )
        for attribute in self.filtered(lambda r: not r.attribute_code):
            code_valid = format_attribute_codes(str(attribute.name))
            if code_valid in valid_attr_codes:
                code_valid += "_duplicated"
            valid_attr_codes.append(code_valid)

            if valid_attr_codes:
                attribute.attribute_code = code_valid
                codes_generated.append(code_valid)
