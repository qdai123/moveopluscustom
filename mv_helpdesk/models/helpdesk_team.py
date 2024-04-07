# -*- coding: utf-8 -*-
from odoo import api, fields, models


class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    use_website_helpdesk_warranty_activation = fields.Boolean(
        string="Website Warranty Activation",
        compute="_compute_use_website_helpdesk_warranty_activation",
        readonly=False,
        store=True,
    )

    @api.depends(
        "use_website_helpdesk_knowledge",
        "use_website_helpdesk_slides",
        "use_website_helpdesk_forum",
        "use_website_helpdesk_warranty_activation"
    )
    def _compute_use_website_helpdesk_form(self):
        # Override to add new arguments to the method's Dependency
        teams = self.filtered(
            lambda team: not team.use_website_helpdesk_form
                         and (
                                 team.use_website_helpdesk_knowledge
                                 or team.use_website_helpdesk_slides
                                 or team.use_website_helpdesk_forum
                                 or team.use_website_helpdesk_warranty_activation
                         )
        )
        teams.use_website_helpdesk_form = True

    @api.depends("use_website_helpdesk_warranty_activation")
    def _compute_use_website_helpdesk_warranty_activation(self):
        warranty_activation = self.filtered("use_website_helpdesk_warranty_activation")
        warranty_activation.update({"use_website_helpdesk_warranty_activation": True})

    @api.model
    def _get_field_modules(self):
        field_modules = super(HelpdeskTeam, self)._get_field_modules()
        # Override to add new "website_helpdesk_warranty_activation"
        field_modules.update({"use_website_helpdesk_warranty_activation": "website_helpdesk_warranty_activation"})
        return field_modules
