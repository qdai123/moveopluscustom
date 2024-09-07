# -*- coding: utf-8 -*-
from odoo.addons.http_routing.models.ir_http import slug
from odoo.addons.mv_helpdesk.models.helpdesk_ticket import (
    END_USER_CODE,
    SUB_DEALER_CODE,
)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HelpdeskTeam(models.Model):
    _inherit = "helpdesk.team"

    @api.model
    def get_activation_warranty_ticket_type_subdealer(self):
        """Get the ticket type for activation warranty [Subdealer]."""
        return self.env.ref(
            "mv_helpdesk.type_guarantee_activation_for_sub_dealer",
            raise_if_not_found=False,
        )

    @api.model
    def get_activation_warranty_ticket_type_end_user(self):
        """Get the ticket type for activation warranty [End User]."""
        return self.env.ref(
            "mv_helpdesk.type_guarantee_activation_for_end_user",
            raise_if_not_found=False,
        )

    @api.model
    def get_claim_warranty_ticket_type(self):
        """Get the ticket type for claiming warranty."""
        return self.env.ref(
            "mv_website_helpdesk.mv_helpdesk_claim_warranty",
            raise_if_not_found=False,
        )

    use_website_helpdesk_warranty_activation = fields.Boolean(
        string="Website Warranty Activation",
        compute="_compute_use_website_helpdesk_warranty_activation",
        readonly=False,
        store=True,
    )

    def _compute_website_url(self):
        super(HelpdeskTeam, self)._compute_website_url()
        for team in self:
            if team.use_website_helpdesk_warranty_activation:
                team.website_url = "/kich-hoat-bao-hanh"
            else:
                team.website_url = "/helpdesk/%s" % slug(team)

    @api.onchange(
        "use_website_helpdesk_form",
        "use_website_helpdesk_forum",
        "use_website_helpdesk_slides",
        "use_website_helpdesk_knowledge",
        "use_website_helpdesk_warranty_activation",
    )
    def _onchange_use_website_helpdesk(self):
        if self.use_website_helpdesk_warranty_activation:
            self.is_published = True
        else:
            if (
                not (
                    self.use_website_helpdesk_form
                    or self.use_website_helpdesk_forum
                    or self.use_website_helpdesk_slides
                    or self.use_website_helpdesk_knowledge
                )
                and self.website_published
            ):
                self.is_published = False
            elif self.use_website_helpdesk_form and not self.website_published:
                self.is_published = True

    @api.depends(
        "name",
        "use_website_helpdesk_form",
        "use_website_helpdesk_warranty_activation",
        "company_id",
    )
    def _compute_form_url(self):
        for team in self:
            base_url = team.get_base_url()
            if (
                team.use_website_helpdesk_form
                and not team.use_website_helpdesk_warranty_activation
            ):
                team.feature_form_url = (
                    (team.use_website_helpdesk_form and team.name and team.id)
                    and (base_url + "/helpdesk/" + slug(team))
                    or False
                )
            elif (
                team.use_website_helpdesk_warranty_activation
                and not team.use_website_helpdesk_form
            ):
                team.feature_form_url = (
                    (
                        team.use_website_helpdesk_warranty_activation
                        and team.name
                        and team.id
                    )
                    and (base_url + "/kich-hoat-bao-hanh")
                    or False
                )

    @api.depends(
        "use_website_helpdesk_knowledge",
        "use_website_helpdesk_slides",
        "use_website_helpdesk_forum",
        "use_website_helpdesk_warranty_activation",
    )
    def _compute_use_website_helpdesk_form(self):
        # Override to add new CASE "website_helpdesk_warranty_activation"
        teams = self.filtered(
            lambda team: not team.use_website_helpdesk_form
            and not team.use_website_helpdesk_warranty_activation
            and (
                team.use_website_helpdesk_knowledge
                or team.use_website_helpdesk_slides
                or team.use_website_helpdesk_forum
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
        field_modules.update(
            {
                "use_website_helpdesk_warranty_activation": "website_helpdesk_warranty_activation"
            }
        )
        return field_modules

    @api.constrains(
        "use_website_helpdesk_form",
        "use_website_helpdesk_warranty_activation",
        "website_id",
        "company_id",
    )
    def _check_website_company(self):
        # Override to add new CASE "website_helpdesk_warranty_activation"
        if any(
            (t.use_website_helpdesk_form or t.use_website_helpdesk_warranty_activation)
            and t.website_id
            and t.website_id.company_id != t.company_id
            for t in self
        ):
            raise ValidationError(
                _("The team company and the website company should match")
            )

    def _ensure_website_menu(self):
        with_website_warranty = self.filtered_domain(
            [("use_website_helpdesk_warranty_activation", "=", True)]
        )
        if with_website_warranty:
            if not with_website_warranty.is_published:
                with_website_warranty.is_published = True
                pass
        else:
            return super(HelpdeskTeam, self)._ensure_website_menu()


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    def _default_team_id(self):
        team_id = (
            self.env["helpdesk.team"]
            .search(
                [
                    ("member_ids", "in", self.env.uid),
                    ("use_website_helpdesk_warranty_activation", "=", True),
                ],
                limit=1,
            )
            .id
        )
        if not team_id:
            team_id = self.env["helpdesk.team"].search([], limit=1).id
        return team_id

    team_id = fields.Many2one(
        comodel_name="helpdesk.team",
        string="Helpdesk Team",
        default=_default_team_id,
        index=True,
        tracking=True,
    )
    ticket_warranty_activation = fields.Boolean(
        compute="_compute_ticket_warranty_activation",
        string="Warranty Ticket",
        store=True,
    )

    @api.depends("team_id", "team_id.use_website_helpdesk_warranty_activation")
    def _compute_ticket_warranty_activation(self):
        """
        Compute the ticket_warranty_activation field based on the team_id's use_website_helpdesk_warranty_activation field.
        Sets the ticket_warranty_activation field to True if the team_id is set and the team uses website helpdesk warranty activation.
        """
        for ticket in self:
            ticket.ticket_warranty_activation = (
                ticket.team_id
                and ticket.team_id.use_website_helpdesk_warranty_activation
            )

    @api.onchange("team_id")
    def onchange_team_id(self):
        if not self.team_id:
            self.write({"ticket_type_id": False})
            return {"domain": {"ticket_type_id": []}}

        ticket_type_domain = [
            (
                "user_for_warranty_activation",
                "=",
                self.team_id.use_website_helpdesk_warranty_activation,
            ),
            (
                "code",
                (
                    "in"
                    if self.team_id.use_website_helpdesk_warranty_activation
                    else "not in"
                ),
                [SUB_DEALER_CODE, END_USER_CODE],
            ),
        ]

        return {"domain": {"ticket_type_id": ticket_type_domain}}
