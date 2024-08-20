# -*- coding: utf-8 -*-
from odoo import fields, models


class Partner(models.Model):
    _inherit = "res.partner"

    mv_partner_survey_ids = fields.One2many(
        "mv.partner.survey",
        "partner_id",
        "Surveys",
        readonly=True,
        copy=False,
    )
