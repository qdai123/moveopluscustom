# -*- coding: utf-8 -*-
from odoo import _, models


class MVPartnerSurveyPublic(models.Model):
    _name = "mv.partner.survey.public"
    _description = _("MV Public Partner Survey")
    _inherit = ["mv.partner.survey"]
    _order = "create_date desc"
    _auto = False
    _log_access = True  # Include magic fields
