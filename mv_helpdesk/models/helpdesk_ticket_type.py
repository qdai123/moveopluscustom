# -*- coding: utf-8 -*-
import logging

from odoo.addons.mv_helpdesk.models.helpdesk_ticket import (
    END_USER_CODE,
    HELPDESK_MANAGER,
    SUB_DEALER_CODE,
)

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HelpdeskTicketType(models.Model):
    _inherit = "helpdesk.ticket.type"

    @api.depends_context("uid")
    def _compute_access_for(self):
        user = self.env.user
        is_admin = self.env.is_admin() or self.env.is_superuser()
        can_edit = user.has_group(HELPDESK_MANAGER) or is_admin

        for record in self:
            record.can_edit = can_edit
            record.can_delete = is_admin

    # ACCESS / RULE Fields:
    can_edit = fields.Boolean("Edit?", compute="_compute_access_for")
    can_delete = fields.Boolean("Delete?", compute="_compute_access_for")

    active = fields.Boolean("Active", default=True)
    user_for_warranty_activation = fields.Boolean(
        "User for Warranty Activation?",
        compute="_compute_for_activation_warranty",
        store=True,
    )
    code = fields.Char(size=64, index=True, help="Helps clearly identify ticket type")

    # ===============================
    # ORM Methods
    # ===============================

    def unlink(self):
        for record in self:
            if (
                not record.can_delete
                and record.user_for_warranty_activation
                and record.code in [SUB_DEALER_CODE, END_USER_CODE]
            ):
                raise UserError(
                    _(
                        f"You cannot delete a type {record.name}. Please contact the administrator."
                    )
                )
        return super().unlink()

    # ==================================
    # COMPUTE / CONSTRAINS Methods
    # ==================================

    @api.depends("code")
    def _compute_for_activation_warranty(self):
        activation_codes = {SUB_DEALER_CODE, END_USER_CODE}
        for record in self:
            record.user_for_warranty_activation = record.code in activation_codes

    @api.constrains("name", "code", "user_for_warranty_activation")
    def _check_codes_already_exist(self):
        for record in self:
            record_exists = self.env["helpdesk.ticket.type"].search_count(
                [
                    ("id", "!=", record.id),
                    ("user_for_warranty_activation", "=", True),
                    (
                        "code",
                        "in",
                        [SUB_DEALER_CODE, END_USER_CODE],
                    ),
                ]
            )
            if record_exists > 1:
                # raise ValidationError(
                #     _(
                #         f"Another type with the same name '{record.name}' already exists."
                #     )
                # )
                _logger.error(
                    f"Another type with the same name '{record.name}' already exists."
                )
                pass
                # TODO: This functional needs to be re-check and fix - Phat Dang <phat.dangminh@moveoplus.com>
