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
            for line in self.line_ids:
                line.send_zns_message()

        return False
