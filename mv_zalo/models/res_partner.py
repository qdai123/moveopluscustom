# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class Partner(models.Model):
    _inherit = "res.partner"

    # === FIELDS ===#
    short_name = fields.Char(
        "Nickname",
        compute="_compute_short_name",
        store=True,
        readonly=False,
        recursive=True,
    )

    @api.depends("name", "parent_id.short_name")
    def _compute_short_name(self):
        for partner in self.filtered(lambda p: not p.short_name):
            partner.short_name = (
                partner.parent_id.short_name
                if partner.parent_id and partner.parent_id.short_name
                else partner.name
            )

    # /// ACTIONS (SERVER) ///

    @api.model
    def action_recompute_methods(self):
        """Recompute methods:
        - short_name
        """
        recompute = super().action_recompute_methods()

        if not self:
            _logger.info("No records to recompute.")
            return False

        try:
            # Recompute "short_name" for all records in the set
            self._compute_short_name()
            _logger.info("Successfully recomputed methods for %s", self)
        except Exception as e:
            _logger.error("Error recomputing methods for %s: %s", self, e)
            return False

        return recompute
