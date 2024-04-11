# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.mv_helpdesk.models.helpdesk_ticket import ticket_type_sub_dealer, ticket_type_end_user


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
        # Override to add new CASE "website_helpdesk_warranty_activation"
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
        # Override to add new CASE "website_helpdesk_warranty_activation"
        field_modules.update({"use_website_helpdesk_warranty_activation": "website_helpdesk_warranty_activation"})
        return field_modules

    @api.constrains(
        "use_website_helpdesk_form",
        "use_website_helpdesk_warranty_activation",
        "website_id",
        "company_id"
    )
    def _check_website_company(self):
        # Override to add new CASE "website_helpdesk_warranty_activation"
        if any(
                (t.use_website_helpdesk_form
                or t.use_website_helpdesk_warranty_activation)
                and t.website_id
                and t.website_id.company_id != t.company_id
                for t in self
        ):
            raise ValidationError(_("The team company and the website company should match"))


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    def _default_team_id(self):
        team_id = self.env["helpdesk.team"].search([
            ("member_ids", "in", self.env.uid),
            ("use_website_helpdesk_warranty_activation", "=", True)
        ], limit=1).id
        if not team_id:
            team_id = self.env["helpdesk.team"].search([], limit=1).id
        return team_id

    team_id = fields.Many2one(
        comodel_name="helpdesk.team",
        string='Helpdesk Team',
        default=_default_team_id,
        index=True,
        tracking=True,
    )
    ticket_warranty_activation = fields.Boolean(
        compute="_compute_ticket_warranty_activation",
        string="Warranty Ticket",
        store=True,
    )

    @api.onchange("team_id", "ticket_warranty_activation")
    def onchange_team_id(self):
        if self.team_id and self.team_id.use_website_helpdesk_warranty_activation and self.ticket_warranty_activation:
            domain = ["|", ("name", "=", ticket_type_sub_dealer), ("name", "=", ticket_type_end_user)]
            return {"domain": {"ticket_type_id": domain}}

    @api.depends("team_id", "team_id.use_website_helpdesk_warranty_activation")
    def _compute_ticket_warranty_activation(self):
        for ticket in self:
            ticket.ticket_warranty_activation = False
            if ticket.team_id and ticket.team_id.use_website_helpdesk_warranty_activation:
                ticket.ticket_warranty_activation = True
                ticket.onchange_team_id()
