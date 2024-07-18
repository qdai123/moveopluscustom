# -*- coding: utf-8 -*-
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class Partner(models.Model):
    _inherit = "res.partner"

    # /// ACTIONS ///

    @api.model
    def action_recompute_methods(self):
        """Recompute methods:
        - user_id
        - tz_offset
        - complete_name
        """
        if not self:
            _logger.info("No records to recompute.")
            return False

        try:
            for partner in self:
                partner._compute_user_id()
                partner._compute_tz_offset()
                partner._compute_complete_name()
            _logger.info("Successfully recomputed methods for %s", self)
        except Exception as e:
            _logger.error("Error recomputing methods for %s: %s", self, e)
            return False
