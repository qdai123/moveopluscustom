# -*- coding: utf-8 -*-
from odoo import _, fields, models


class MvBrandProportion(models.Model):
    """Brand Proportion for Partner Survey"""

    _name = "mv.brand.proportion"
    _description = _("Brand Proportion")

    partner_survey_id = fields.Many2one(
        "mv.partner.survey",
        "Phiếu khảo sát",
        required=True,
        index=True,
        ondelete="restrict",
    )
    brand_id = fields.Many2one("mv.brand", "Hãng lốp")
    year_participation = fields.Char("Năm tham gia", required=True, size=10)
    proportion = fields.Float("Tỷ trọng", default=0)
    quantity_per_month = fields.Integer("Số lượng quả/tháng", default=0)

    _sql_constraints = [
        (
            "mv_brand_proportion_unique",
            "unique(partner_survey_id, brand_id)",
            "Không được tạo dữ liệu trùng lặp cho cùng Phiếu khảo sát, Thương hiệu.",
        )
    ]
