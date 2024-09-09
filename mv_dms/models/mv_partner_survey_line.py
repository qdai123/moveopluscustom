# -*- coding: utf-8 -*-
from odoo import models


class MvPartnerSurveyLine(models.Model):
    _name = "mv.partner.survey.line"
    _description = _("Partner Survey Line")
    _rec_names_search = ["name", "partner_survey_id.name"]
    _order = "partner_survey_id,  sequence, id"
    _check_company_auto = True

    partner_survey_id = fields.Many2one(
        "mv.partner.survey",
        "Survey",
        required=True,
        ondelete="cascade",
        index=True,
        copy=False,
    )
    sequence = fields.Integer("Sequence", default=10)

    # Partner Survey-related fields
    company_id = fields.Many2one(
        related="partner_survey_id.company_id",
        store=True,
        index=True,
        precompute=True,
    )
    currency_id = fields.Many2one(
        related="partner_survey_id.currency_id",
        depends=["partner_survey_id.currency_id"],
        store=True,
        precompute=True,
    )
    order_partner_id = fields.Many2one(
        related="partner_survey_id.partner_id",
        store=True,
        index=True,
        precompute=True,
    )
    surveyor_id = fields.Many2one(
        related="partner_survey_id.create_uid",
        store=True,
        precompute=True,
    )
    state = fields.Selection(
        related="partner_survey_id.state",
        copy=False,
        store=True,
        precompute=True,
    )
    region_id = fields.Many2one(
        related="partner_survey_id.region_id",
        copy=False,
        store=True,
        precompute=True,
    )
