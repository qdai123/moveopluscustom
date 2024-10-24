# -*- coding: utf-8 -*-
import json
import logging

from odoo.addons.biz_zalo_common.models.common import (
    get_datetime,
)
from odoo.addons.mv_zalo.core.zalo_notification_service import (
    CODE_ERROR_ZNS,
    ZNS_CKKH_POLICY_NOTIFICATION_TEMPLATE,
    ZNS_GET_DATA_BY_TEMPLATE,
    ZNS_GET_PAYLOAD,
    zns_convert_valid_phonenumber,
)

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class MvComputeWarrantyDiscountPolicyLine(models.Model):
    _inherit = "mv.compute.warranty.discount.policy.line"

    @api.model
    def _get_zns_template(self):
        ICPSudo = self.env["ir.config_parameter"].sudo()
        return ICPSudo.get_param(ZNS_CKKH_POLICY_NOTIFICATION_TEMPLATE, "")

    # === ZALO ZNS FIELDS ===#
    zns_notification_sent = fields.Boolean(
        "ZNS Notification Sent", default=False, readonly=True
    )
    zns_history_id = fields.Many2one("zns.history", "ZNS History", readonly=True)
    zns_history_status = fields.Selection(
        related="zns_history_id.status", string="ZNS History Status"
    )

    # === PARTNER FIELDS for ZNS ===#
    short_name = fields.Char(related="partner_id.short_name", store=True)
    partner_phone = fields.Char(related="partner_id.phone", store=True)
    partner_mobile = fields.Char(related="partner_id.mobile", store=True)
    partner_company_registry = fields.Char(
        related="partner_id.company_registry", store=True
    )
    partner_total_discount_amount = fields.Float(
        "Total Discount Amount (Month)", compute="_compute_amount_update", store=True
    )
    partner_discount_amount_update = fields.Float(
        "Partner Discount Amount (UPDATE)", compute="_compute_amount_update", store=True
    )

    @api.depends("partner_id", "partner_id.amount_currency", "total_amount_currency")
    def _compute_amount_update(self):
        for record in self:
            record.partner_total_discount_amount = record.total_amount_currency
            record.partner_discount_amount_update = (
                record.partner_id.amount_currency + record.partner_total_discount_amount
            )

    # /// ACTIONS ///

    def action_send_message_zns(self):
        self.ensure_one()

        if not self.partner_id:
            return

        phone_number = self.partner_mobile or self.partner_id.mobile
        if not phone_number:
            _logger.error("Partner has no phone number.")
            return

        valid_phone_number = zns_convert_valid_phonenumber(phone_number)
        if not valid_phone_number:
            _logger.error("Invalid phone number for partner")
            return

        self._compute_amount_update()  # Recompute the discount amount

        # Prepare the context for the wizard view
        view_id = self.env.ref("biz_zalo_zns.view_zns_send_message_wizard_form")
        if not view_id:
            _logger.error(
                "View 'biz_zalo_zns.view_zns_send_message_wizard_form' not found."
            )
            return

        # ZNS Template:
        zns_template = self.env["zns.template"].search(
            [
                ("active", "=", True),
                ("sample_data", "!=", False),
                ("use_type", "=", self._name),
            ],
            limit=1,
        )

        context = {
            "default_template_id": zns_template.id if zns_template else False,
            "default_phone": valid_phone_number,
            "default_use_type": self._name,
            "default_tracking_id": self.id,
            "default_mv_compute_warranty_discount_id": self.parent_id.id,
            "default_mv_compute_warranty_discount_line_id": self.id,
        }

        # Return the action dictionary to open the wizard form view
        return {
            "name": _("Send Message ZNS"),
            "type": "ir.actions.act_window",
            "res_model": "zns.send.message.wizard",
            "view_id": view_id.id,
            "views": [(view_id.id, "form")],
            "context": context,
            "target": "new",
        }

    # /// ZALO ZNS ///

    def send_zns_message(self):
        # Retrieve ZNS configuration
        ZNSConfiguration = self._retrieve_zns_configuration()
        if not ZNSConfiguration:
            _logger.error("ZNS Configuration is not found!")
            return

        template_id = self._get_zns_template()
        if not template_id:
            _logger.error("ZNS Notification Template not found.")
            return

        zns_template = self.env["zns.template"].search(
            [("template_id", "=", template_id)], limit=1
        )
        if not zns_template:
            _logger.error(f"ZNS Template with ID {template_id} not found.")
            return

        _logger.info(
            f">>> ZNS Template: [{zns_template.template_id}] {zns_template.template_name} <<<"
        )

        zns_sample_data = self.env["zns.template.sample.data"].search(
            [("zns_template_id", "=", zns_template.id)]
        )
        if not zns_sample_data:
            _logger.error("ZNS Template Sample Data not found.")
            return

        template_data_sample = {
            sample_data.name: (
                sample_data.value
                if not sample_data.field_id
                else ZNS_GET_DATA_BY_TEMPLATE(sample_data, self)
            )
            for sample_data in zns_sample_data
        }

        # Extract data
        phone = zns_convert_valid_phonenumber(
            self.partner_mobile or self.partner_id.mobile
        )
        tracking_id = self.id
        template_id = zns_template.template_id
        template_data = json.dumps(template_data_sample)

        # Execute ZNS request
        _, response_data = self.env["zalo.log.request"].do_execute(
            ZNSConfiguration._get_sub_url_zns("/message/template"),
            method="POST",
            headers=ZNSConfiguration._get_headers(),
            payload=ZNS_GET_PAYLOAD(
                phone, template_id, json.loads(template_data), tracking_id
            ),
            is_check=True,
        )

        # Handle empty response
        if not response_data:
            _logger.error("No data received.")
            return

        # Handle error response
        if response_data["error"] != 0 and response_data["message"] != "Success":
            error_message = CODE_ERROR_ZNS.get(
                str(response_data["error"]), "Unknown error"
            )
            _logger.error(
                f"ZNS Code Error: {response_data['error']}, Error Info: {error_message}"
            )
            return

        # Process successful response
        if response_data.get("data"):
            self.generate_zns_history(response_data.get("data"), ZNSConfiguration)
            self.zns_notification_sent = True

            _logger.info(
                f">>> Send Message ZNS successfully for Partner: {self.partner_id.name} <<<"
            )

    def _retrieve_zns_configuration(self):
        ZNSConfiguration = self.env["zalo.config"].search(
            [("primary_settings", "=", True)], limit=1
        )
        if not ZNSConfiguration:
            _logger.error("ZNS Configuration is not found!")
            return None
        return ZNSConfiguration

    def generate_zns_history(self, data, config_id=False):
        template_id = self._get_zns_template()
        if not template_id or template_id is None:
            _logger.error("ZNS Notification Template not found.")
            return False

        zns_template_id = self.env["zns.template"].search(
            [("template_id", "=", template_id)], limit=1
        )
        zns_history_id = self.env["zns.history"].search(
            [("msg_id", "=", data.get("msg_id"))], limit=1
        )
        sent_time = (
            get_datetime(data.get("sent_time", False))
            if data.get("sent_time", False)
            else ""
        )

        if not zns_history_id:
            origin = self.parent_name
            zns_history_id = zns_history_id.create(
                {
                    "msg_id": data.get("msg_id"),
                    "origin": origin,
                    "sent_time": sent_time,
                    "zalo_config_id": config_id and config_id.id or False,
                    "partner_id": self.partner_id.id if self.partner_id else False,
                    "template_id": zns_template_id.id,
                }
            )
        if zns_history_id and zns_history_id.template_id:
            remaining_quota = (
                data.get("quota")["remainingQuota"]
                if data.get("quota") and data.get("quota").get("remainingQuota")
                else 0
            )
            daily_quota = (
                data.get("quota")["dailyQuota"]
                if data.get("quota") and data.get("quota").get("dailyQuota")
                else 0
            )
            zns_history_id.template_id.update_quota(daily_quota, remaining_quota)
            zns_history_id.get_message_status()

        self.zns_history_id = zns_history_id.id if zns_history_id else False
