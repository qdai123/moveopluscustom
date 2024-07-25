# -*- coding: utf-8 -*-
from odoo import models


class MvComputeWarrantyDiscountPolicy(models.Model):
    _inherit = "mv.compute.warranty.discount.policy"

    # =================================
    # BUSINESS Methods (OVERRIDE)
    # =================================

    def action_done(self):
        super(MvComputeWarrantyDiscountPolicy, self).action_done()

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
                line.send_zns_message()
                line.partner_id.sudo().action_update_discount_amount()

        return False
