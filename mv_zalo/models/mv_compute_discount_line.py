# -*- coding: utf-8 -*-
import json
import logging

import pytz
from markupsafe import Markup
from odoo.addons.biz_zalo_common.models.common import (
    CODE_ERROR_ZNS,
    convert_valid_phone_number,
    get_datetime,
)
from odoo.addons.mv_zalo.zalo_oa_functional import (
    ZNS_GENERATE_MESSAGE,
    ZNS_GET_PAYLOAD,
)

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

CODE_ERROR_ZNS = dict(CODE_ERROR_ZNS)


def get_zns_time(time, user_timezone="Asia/Ho_Chi_Minh"):
    """
    Converts a given datetime object to the specified timezone.

    Parameters:
    - time (datetime): A timezone-aware datetime object.
    - user_timezone (str): The name of the timezone to convert `time` to. Defaults to 'Asia/Ho_Chi_Minh'.

    Returns:
    - datetime: The converted datetime object in the specified timezone.
    """
    try:
        user_tz = pytz.timezone(user_timezone)
        return time.astimezone(user_tz)
    except (pytz.UnknownTimeZoneError, ValueError) as e:
        _logger.error(f"Error converting ZNS Timezone: {e}")
        return None


class MvComputeDiscountLine(models.Model):
    _inherit = "mv.compute.discount.line"

    @api.model
    def _get_zns_compute_discount_ckt_notification_template(self):
        ICPSudo = self.env["ir.config_parameter"].sudo()
        return ICPSudo.get_param(
            "mv_zalo.zns_compute_discount_ckt_notification_template", ""
        )

    # === ZALO ZNS FIELDS ===#
    zns_notification_sent = fields.Boolean(
        "ZNS Notification Sent", default=False, readonly=True
    )
    zns_history_id = fields.Many2one("zns.history", "ZNS History", readonly=True)
    zns_history_status = fields.Selection(
        related="zns_history_id.status", string="ZNS History Status"
    )

    # === PARTNER FIELDS ===#
    short_name = fields.Char(related="partner_id.short_name", store=True)
    partner_phone = fields.Char(related="partner_id.phone", store=True)

    # /// ZALO ZNS ///

    def send_zns_message(self):
        # Retrieve ZNS configuration
        ZNSConfiguration = self._retrieve_zns_configuration()
        if not ZNSConfiguration:
            _logger.error("ZNS Configuration is not found!")
            return

        template_id = self._get_zns_compute_discount_ckt_notification_template()
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
                else self._get_sample_data_by(sample_data, self)
            )
            for sample_data in zns_sample_data
        }

        # Extract data
        phone = convert_valid_phone_number(self.partner_phone)
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
            for r_data in response_data["data"]:
                sent_time = (
                    get_datetime(r_data["sent_time"]) if r_data["sent_time"] else ""
                )
                formatted_sent_time = get_zns_time(sent_time) if sent_time else ""
                zns_message = ZNS_GENERATE_MESSAGE(r_data, formatted_sent_time)
                self.generate_zns_history(r_data, ZNSConfiguration)
                self.parent_id.message_post(body=Markup(zns_message))
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
        template_id = self._get_zns_compute_discount_ckt_notification_template()
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
            origin = self.name
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

    def _get_sample_data_by(self, sample_id, obj):
        # Check if the 'field_id' is set
        if not sample_id.field_id:
            _logger.error("Field ID not found for sample_id: {}".format(sample_id))
            return None

        field_name = sample_id.field_id.name
        field_type = sample_id.field_id.ttype
        sample_type = sample_id.type
        value = obj[field_name]

        _logger.debug(
            f"Processing Field: {field_name}, Type: {field_type}, Sample Type: {sample_type}"
        )

        try:
            if field_type in ["date", "datetime"] and sample_type == "DATE":
                return value.strftime("%d/%m/%Y") if value else None
            elif (
                field_type in ["float", "integer", "monetary"]
                and sample_type == "NUMBER"
            ):
                return str(value)
            elif field_type in ["char", "text"] and sample_type == "STRING":
                return value if value else None
            elif field_type == "many2one" and sample_type == "STRING":
                return str(value.name) if value else None
            else:
                _logger.error(
                    f"Unhandled field type: {field_type} or sample type: {sample_type}"
                )
                return None
        except Exception as e:
            _logger.error(f"Error processing sample data for {field_name}: {e}")
            return None
