# -*- coding: utf-8 -*-
import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)

DISCOUNT_PERCENTAGE_DIVISOR = 100


class MvWizardQuickCreatePartnerSurvey(models.TransientModel):
    _name = "mv.wizard.quick.create.partner.survey"
    _description = _("Wizard: Quick Create Partner Survey")

    partner_id = fields.Many2one("res.partner", string="Partner", required=True)
