# -*- coding: utf-8 -*-
from odoo import api, models


class Users(models.Model):
    _inherit = "res.users"

    @api.model
    def get_surveys_by_partner(self):
        # Check if the user is a Portal User or an Internal User
        if self.has_group("base.group_portal") or self.has_group("base.group_user"):
            # Fetch all surveys related to the partner associated with the user
            partner_id = self.partner_id.id
            surveys = self.env["mv.partner.survey"].search(
                [("partner_id", "=", partner_id)]
            )
            return surveys
        return []
