# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    zns_payment_notification_template_id = fields.Many2one(
        "zns.template",
        "ZNS Payment Notification Template",
        domain="[('use_type', 'in', ['account.move'])]",
    )
    zns_template_id = fields.Integer(
        default=0,
        config_parameter="mv_zalo.zns_payment_notification_template_id",
    )

    @api.onchange("zns_payment_notification_template_id")
    def _onchange_zns_payment_notification_template_id(self):
        if self.zns_payment_notification_template_id:
            self.zns_template_id = self.zns_payment_notification_template_id.id

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        ICPSudo = self.env["ir.config_parameter"].sudo()
        zns_template_id = ICPSudo.get_param(
            "mv_zalo.zns_payment_notification_template_id", False
        )
        res.update(zns_template_id=zns_template_id)
        return res

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        ICPSudo = self.env["ir.config_parameter"].sudo()
        ICPSudo.set_param(
            "mv_zalo.zns_payment_notification_template_id", self.zns_template_id
        )
