# -*- coding: utf-8 -*-
import logging
from unidecode import unidecode

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def format_attribute_codes(text):
    # Chuyển từ có dấu sang không dấu
    text = unidecode(text)
    # Chuyển thành chữ thường
    text = text.lower()
    # Thay thế khoảng trắng bằng dấu gạch dưới
    text = text.replace(" ", "_")
    # Loại bỏ các dấu ngoặc và giữ nguyên đơn vị đo lường
    text = text.replace("(", "").replace(")", "")
    return text


class ProductAttribute(models.Model):
    _inherit = "product.attribute"

    warranty_discount_policy_ids = fields.Many2many(
        "mv.warranty.discount.policy",
        "mv_warranty_discount_product_attribute_rel",
        "mv_warranty_discount_policy_id",
        "product_attribute_id",
        string="Chính sách chiết khấu kích hoạt",
        help="Parent Model: mv.warranty.discount.policy",
    )
    attribute_code = fields.Char("Code", copy=False)

    _sql_constraints = [
        (
            "attribute_code_uniq",
            "unique(attribute_code)",
            "A code with the same name already exists for this property. Please use another code.",
        )
    ]

    def action_generate_attribute_code(self):
        # [!] Remove all attribute_code before generate new one
        self.filtered(lambda r: r.attribute_code).write({"attribute_code": None})

        codes_generated = (
            self.env["product.attribute"].search([]).mapped("attribute_code")
        )
        for attribute in self.filtered(lambda r: not r.attribute_code):
            try:
                code_valid = format_attribute_codes(str(attribute.name))
                if code_valid in codes_generated:
                    attribute.attribute_code = code_valid + "_duplicated"
                else:
                    attribute.attribute_code = code_valid
                    codes_generated.append(code_valid)
            except Exception as e:
                _logger.error(
                    "Failed to generate attribute code for attribute %s: %s",
                    attribute.name,
                    e,
                )
