# -*- coding: utf-8 -*-
from odoo import models


class MvComputeDiscount(models.Model):
    _inherit = "mv.compute.discount"

    # =================================
    # BUSINESS Methods (OVERRIDE)
    # =================================

    def action_done(self):
        super(MvComputeDiscount, self).action_done()

        for record in self:
            # [>] Send ZNS Notification to Partner Agency
            record.send_zns_notification()

        return True

    # =================================
    # ZALO ZNS Methods
    # =================================

    def send_zns_notification(self):
        if self.line_ids:
            for line in self.line_ids:
                line.send_zns_message()

        return False
