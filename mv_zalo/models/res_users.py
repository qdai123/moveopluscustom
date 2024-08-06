# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

ZALO_OA_MANAGER = "mv_zalo.group_mv_zalo_manager"
ZALO_OA_USER = "mv_zalo.group_mv_zalo_user"


class Users(models.Model):
    _inherit = "res.users"

    # === Permission Fields ===#
    is_zalo_manager = fields.Boolean(compute="_compute_permissions")
    is_zalo_user = fields.Boolean(compute="_compute_permissions")

    @api.depends_context("uid")
    def _compute_permissions(self):
        for user in self:
            user.is_zalo_manager = user.has_group(ZALO_OA_MANAGER)
            user.is_zalo_user = not user.is_zalo_manager and user.has_group(
                ZALO_OA_USER
            )
