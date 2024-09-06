# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


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
    brand_id = fields.Many2one("mv.brand", index=True)
    year_participation = fields.Char("Năm tham gia", required=True, size=10)
    proportion = fields.Float("Tỷ trọng", compute="_compute_proportion", store=True)
    quantity_per_month = fields.Integer("Số lượng quả/tháng", default=0)

    _sql_constraints = [
        (
            "brand_year_participation_unique",
            "UNIQUE(brand_id, year_participation)",
            "Hãng lốp và năm tham gia phải là duy nhất!",
        ),
    ]

    @api.depends(
        "partner_survey_id",
        "partner_survey_id.total_quantity_brand_proportion",
        "quantity_per_month",
    )
    def _compute_proportion(self):
        """
        Compute the proportion of the brand based on the quantity per month and the total quantity.

        This method calculates the proportion of the brand for the partner survey and updates the
        `proportion` field accordingly.

        :return: None
        """
        for record in self:
            if (
                record.partner_survey_id
                and record.partner_survey_id.total_quantity_brand_proportion
            ):
                record.proportion = (
                    record.quantity_per_month
                    / record.partner_survey_id.total_quantity_brand_proportion
                ) * 1
            else:
                record.proportion = 0
