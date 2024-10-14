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
    year_participation = fields.Char("Năm tham gia", size=10)
    proportion = fields.Float("Tỷ trọng", compute="_compute_proportion", store=True)
    quantity_per_month = fields.Integer("Số lượng/tháng", default=0)

    _sql_constraints = [
        (
            "partner_survey_brand_year_participation_unique",
            "UNIQUE(partner_survey_id, brand_id, year_participation)",
            "Hãng lốp và năm tham gia phải là duy nhất!",
        )
    ]

    @api.depends(
        "partner_survey_id",
        "partner_survey_id.total_quantity_brand_proportion_of_tire",
        "partner_survey_id.total_quantity_brand_proportion_of_lubricant",
        "partner_survey_id.total_quantity_brand_proportion_battery",
        "quantity_per_month",
    )
    def _compute_proportion(self):
        for record in self:
            has_partner_survey = record.partner_survey_id
            if has_partner_survey.total_quantity_brand_proportion_of_tire:
                if has_partner_survey:
                    record.proportion = (
                                                record.quantity_per_month
                                                / record.partner_survey_id.total_quantity_brand_proportion_of_tire
                                        ) * 1
                elif has_partner_survey.total_quantity_brand_proportion_of_lubricant:
                    record.proportion = (
                                                record.quantity_per_month
                                                / record.partner_survey_id.total_quantity_brand_proportion_of_lubricant
                                        ) * 1
                elif has_partner_survey.total_quantity_brand_proportion_battery:
                    record.proportion = (
                                                record.quantity_per_month
                                                / record.partner_survey_id.total_quantity_brand_proportion_battery
                                        ) * 1
            else:
                record.proportion = 0
