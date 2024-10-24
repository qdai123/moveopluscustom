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
            record.notify_partner_agency()

        return True

    # =================================
    # ZALO ZNS Methods
    # =================================

    def notify_partner_agency(self):
        eligible_lines = self.get_eligible_lines()
        for line in eligible_lines:
            line.sudo().send_zns_message()
            line.sudo().partner_id.action_update_discount_amount()
        return bool(eligible_lines)

    def get_eligible_lines(self):
        return self.line_ids.filtered(
            lambda r: r.partner_id
            and r.partner_id.mobile
            and not r.zns_notification_sent
        )
