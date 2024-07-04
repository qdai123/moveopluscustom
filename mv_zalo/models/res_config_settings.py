# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    zns_payment_notification_template_id = fields.Many2one(
        "zns.template",
        "ZNS Payment Notification Template",
        domain="[('use_type', 'in', ['account.move'])]",
        config_parameter="mv_zalo.zns_payment_notification_template",
    )

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICPSudo = self.env["ir.config_parameter"].sudo()
        ICPSudo.set_param(
            "mv_zalo.zns_payment_notification_template",
            self.zns_payment_notification_template_id,
        )
