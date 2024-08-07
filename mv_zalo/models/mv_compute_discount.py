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
            for line in self.line_ids.filtered(
                lambda r: r.partner_id
                and r.partner_id.mobile
                and not r.zns_notification_sent
            ):
                line.sudo().send_zns_message()
                line.sudo().partner_id.action_update_discount_amount()

        return False
