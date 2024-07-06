# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Users(models.Model):
    _inherit = "res.users"

    # === Permission Fields ===#
    is_zalo_manager = fields.Boolean(compute="_compute_permissions")

    @api.depends_context("uid")
    def _compute_permissions(self):
        for record in self:
            record.is_zalo_manager = False
            if record.has_group("mv_zalo.group_mv_zalo_manager"):
                record.is_zalo_manager = True
            else:
                record.is_zalo_manager = False
            _logger.info(
                f"User {record.name} is_zalo_manager: {record.is_zalo_manager}"
            )
        return True
