# -*- coding: utf-8 -*-
import json
import logging
from datetime import timedelta

import pytz
from markupsafe import Markup
from odoo.addons.biz_zalo_common.models.common import (
    CODE_ERROR_ZNS,
    convert_valid_phone_number,
    get_datetime,
)
from odoo.addons.mv_zalo.zalo_oa_functional import (
    ZNS_GENERATE_MESSAGE,
    ZNS_GET_SAMPLE_DATA,
    ZNS_GET_PAYLOAD,
)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


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


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _get_zns_payment_notification_template(self):
        ICPSudo = self.env["ir.config_parameter"].sudo()
        return ICPSudo.get_param("mv_zalo.zns_payment_notification_template_id", "")

    # === FIELDS ===#
    zns_notification_sent = fields.Boolean(
        "ZNS Notification Sent", default=False, readonly=True
    )
    zns_history_id = fields.Many2one("zns.history", "ZNS History", readonly=True)
    zns_history_status = fields.Selection(
        related="zns_history_id.status", string="ZNS History Status"
    )

    # /// ACTIONS ///

    def action_send_message_zns(self):
        self.ensure_one()

        view_id = self.env.ref("biz_zalo_zns.view_zns_send_message_wizard_form")
        if not view_id:
            _logger.error(
                "View 'biz_zalo_zns.view_zns_send_message_wizard_form' not found."
            )
            return

        invoice = self
        partner = invoice.partner_id

        phone_number = partner.phone if partner else None
        valid_phone_number = (
            convert_valid_phone_number(phone_number) if phone_number else False
        )

        return {
            "name": _("Send Message ZNS"),
            "type": "ir.actions.act_window",
            "res_model": "zns.send.message.wizard",
            "view_id": view_id.id,
            "views": [(view_id.id, "form")],
            "context": {
                "default_use_type": invoice._name,
                "default_tracking_id": invoice.id,
                "default_account_move_id": invoice.id,
                "default_phone": valid_phone_number,
            },
            "target": "new",
        }

    # /// Zalo ZNS ///

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

    def generate_zns_history(self, data, config_id=False):
        template_id = self._get_zns_payment_notification_template()
        if not template_id or template_id is None:
            _logger.error("ZNS Payment Notification Template not found.")
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

    def send_zns_message(self, data, testing=False):
        ZNSConfiguration = self.env["zalo.config"].search(
            [("primary_settings", "=", True)], limit=1
        )
        if not ZNSConfiguration:
            raise ValidationError("ZNS Configuration is not found!")

        # Parameters
        phone = convert_valid_phone_number(data.get("phone"))
        template_id = data.get("template_id")
        template_data = data.get("template_data")
        tracking_id = data.get("tracking_id")

        _, datas = self.env["zalo.log.request"].do_execute(
            ZNSConfiguration._get_sub_url_zns("/message/template"),
            method="POST",
            headers=ZNSConfiguration._get_headers(),
            payload=ZNS_GET_PAYLOAD(
                phone, template_id, json.dumps(template_data), tracking_id
            ),
            is_check=True,
        )

        import pprint

        pprint.pprint(datas, indent=2)

        if datas and isinstance(datas, list) and len(datas) > 0:
            data = datas[0]  # Assuming the first item is the desired one
            if data.get("error") == 0 and data.get("message") == "Success":
                data = datas.get("data")
                if data:
                    sent_time = (
                        get_datetime(data.get("sent_time", False))
                        if data.get("sent_time", False)
                        else ""
                    )
                    sent_time = sent_time and get_zns_time(sent_time) or ""
                    zns_message = ZNS_GENERATE_MESSAGE(data, sent_time)
                    self.generate_zns_history(data, ZNSConfiguration)
                    self.message_post(body=Markup(zns_message))
                    self.zns_notification_sent = True if not testing else False
                    _logger.info(
                        f"Send Message ZNS successfully for Invoice {self.name}!"
                    )
            else:
                error_message = CODE_ERROR_ZNS.get(str(data["error"]), "Unknown error")
                _logger.error(
                    f"Code Error: {data['error']}, Error Info: {error_message}"
                )
        else:
            _logger.error("Unexpected data format or empty response.")

    # /// CRON JOB ///
    @api.model
    def _cron_notification_date_due_journal_entry(self, dt_before=False, phone=False):
        template_id = int(self._get_zns_payment_notification_template())
        if not template_id or template_id is None:
            _logger.error("ZNS Payment Notification Template not found.")
            return

        zns_template_id = self.env["zns.template"].search(
            [("template_id", "=", template_id)], limit=1
        )
        _logger.debug(f">>> ZNS Template ID: {zns_template_id} <<<")

        zns_template_data = {}
        zns_sample_data_ids = self.env["zns.template.sample.data"].search(
            [("zns_template_id", "=", zns_template_id.id)],
        )
        if not zns_sample_data_ids:
            _logger.error("ZNS Template Sample Data not found.")
            return

        for sample_data in zns_sample_data_ids:
            zns_template_data[sample_data.name] = (
                sample_data.value
                if not sample_data.field_id
                else self._get_sample_data_by(sample_data, self)
            )  # TODO: ZNS_GET_SAMPLE_DATA needs to re-check

        phone_test = False
        if phone:
            # Remove any non-digit characters
            digits = "".join(filter(str.isdigit, phone))

            # Check if the number has 10 digits
            if len(digits) not in [10, 11]:
                raise ValidationError(
                    _("Phone number must contain exactly 10 or 11 digits")
                )
            phone_test = digits

        # Get all journal entries that are due in the next 2 days
        # and have not been sent a ZNS notification
        journal_entries = (
            self.env["account.move"]
            .search(
                [
                    ("state", "=", "posted"),
                    ("payment_state", "=", "not_paid"),
                    ("zns_notification_sent", "=", False),
                ]
            )
            .filtered(
                lambda am: fields.Date.today()
                == am.invoice_date_due
                - timedelta(days=int(dt_before) if dt_before else 2)
            )
        )
        if journal_entries:
            for line in journal_entries:
                valid_phone_number = (
                    convert_valid_phone_number(line.partner_id.phone)
                    if not phone
                    else phone_test
                )
                self.send_zns_message(
                    {
                        "phone": valid_phone_number,
                        "template_id": zns_template_id.id,
                        "template_data": zns_template_data,
                        "tracking_id": line.id,
                    }
                )

                _logger.debug(f"Phone: {valid_phone_number}")
                _logger.debug(f"Template ID: {zns_template_id.id}")
                _logger.debug(f"Template Data: {zns_template_data}")
                _logger.debug(f"Tracking ID: {line.id}")

            _logger.info(
                ">>> ZNS: Notification Date Due Journal Entry - SUCCESSFULLY <<<"
            )

        return True
