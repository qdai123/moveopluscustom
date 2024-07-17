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
    ZNS_GET_PAYLOAD,
)

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

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


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def _get_zns_payment_notification_template(self):
        ICPSudo = self.env["ir.config_parameter"].sudo()
        return ICPSudo.get_param("mv_zalo.zns_payment_notification_template_id", "")

    # === INVOICE / PAYMENT FIELDS ===#
    bank_transfer_details = fields.Text(
        compute="_compute_bank_transfer_details", store=True
    )
    payment_early_discount_percentage = fields.Float(
        compute="_compute_payment_early_discount_percentage", store=True
    )
    payment_early_discount_percentage_display = fields.Char(
        compute="_compute_payment_early_discount_percentage",
        string="Early Discount (%)",
        store=True,
    )
    amount_paid_already = fields.Monetary(
        "Paid Amount", compute="_compute_amount_early", store=True
    )
    amount_must_pay = fields.Monetary(
        "Amount Must Pay", compute="_compute_amount_early", store=True
    )

    @api.depends("name", "invoice_payment_term_id")
    def _compute_bank_transfer_details(self):
        for record in self:
            today = fields.Date.today()
            if record.name and record.invoice_payment_term_id:
                record.bank_transfer_details = "THANH TOAN HOA DON {invoice_name}-{year}{month}{day}/{partner_id}".format(
                    invoice_name=record.name,
                    year=today.year,
                    month=today.month,
                    day=today.day,
                    partner_id=record.partner_id.id,
                )

    @api.depends("invoice_payment_term_id", "invoice_payment_term_id.early_discount")
    def _compute_payment_early_discount_percentage(self):
        for record in self:
            if (
                record.invoice_payment_term_id
                and record.invoice_payment_term_id.early_discount
            ):
                record.payment_early_discount_percentage = (
                    record.invoice_payment_term_id.discount_percentage
                )
                record.payment_early_discount_percentage_display = "{discount}%".format(
                    discount=record.payment_early_discount_percentage
                )

    @api.depends("amount_total", "amount_residual")
    def _compute_amount_early(self):
        for record in self:
            record.amount_paid_already = record.amount_total - record.amount_residual
            record.amount_must_pay = (
                record.amount_residual
                if record.amount_residual > 0
                else record.amount_total
            )

    # === PARTNER FIELDS ===#
    short_name = fields.Char(related="partner_id.short_name", store=True)
    partner_phone = fields.Char(related="partner_id.phone", store=True)
    partner_company_registry = fields.Char(
        related="partner_id.company_registry", store=True
    )

    # === ZALO ZNS FIELDS ===#
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

        # Ensure the invoice has an associated partner
        if not self.partner_id:
            _logger.error("Invoice ID %s has no associated partner.", self.id)
            return

        # Validate the partner's phone number
        phone_number = self.partner_id.phone
        if not phone_number:
            _logger.error(
                "Partner associated with Invoice ID %s has no phone number.", self.id
            )
            return
        valid_phone_number = convert_valid_phone_number(phone_number)
        if not valid_phone_number:
            _logger.error(
                "Invalid phone number for partner associated with Invoice ID %s.",
                self.id,
            )
            return

        # Prepare the context for the wizard view
        view_id = self.env.ref("biz_zalo_zns.view_zns_send_message_wizard_form")
        if not view_id:
            _logger.error(
                "View 'biz_zalo_zns.view_zns_send_message_wizard_form' not found."
            )
            return

        context = {
            "default_use_type": self._name,
            "default_tracking_id": self.id,
            "default_account_move_id": self.id,
            "default_phone": valid_phone_number,
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

    # /// CRON JOB ///
    @api.model
    def _cron_notification_invoice_date_due(self, date_before=False, phone=False):
        def sanitize_phone(phonenumber=phone):

            if not phonenumber:
                pass

            digits = "".join(filter(str.isdigit, phonenumber))
            if len(digits) not in [10, 11]:
                raise ValidationError(
                    _("Phone number must contain exactly 10 or 11 digits")
                )
            return digits

        testing_phone = sanitize_phone(phone) if phone else False

        template_id = self._get_zns_payment_notification_template()
        if not template_id:
            _logger.error("ZNS Payment Notification Template not found.")
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

        due_date = fields.Date.today() - timedelta(
            days=int(date_before) if date_before else 2
        )
        journal_entries = self.env["account.move"].search(
            [
                ("state", "=", "posted"),
                ("payment_state", "=", "not_paid"),
                ("zns_notification_sent", "=", False),
                ("invoice_date_due", "=", due_date),
            ]
        )
        for entry in journal_entries:
            valid_phone_number = (
                sanitize_phone(entry.partner_id.phone) if not phone else testing_phone
            )
            template_data = {
                sample_data.name: (
                    sample_data.value
                    if not sample_data.field_id
                    else entry._get_sample_data_by(sample_data, entry)
                )
                for sample_data in zns_sample_data
            }

            # Recompute Invoice Data
            entry._compute_amount_early()
            entry._compute_payment_early_discount_percentage()
            entry._compute_bank_transfer_details()

            entry.send_zns_message(
                {
                    "phone": valid_phone_number,
                    "template_id": zns_template.template_id,
                    "template_data": json.dumps(template_data),
                    "tracking_id": entry.id,
                },
                bool(phone),
            )

        return True

    # /// ZALO ZNS ///

    def send_zns_message(self, data, testing=False):
        # Retrieve ZNS configuration
        ZNSConfiguration = self._retrieve_zns_configuration()
        if not ZNSConfiguration:
            _logger.error("ZNS Configuration is not found!")
            return

        # Extract data
        phone = convert_valid_phone_number(data.get("phone"))
        tracking_id = data.get("tracking_id")
        template_id = data.get("template_id")
        template_data = data.get("template_data")

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
                self.message_post(body=Markup(zns_message))
                self.zns_notification_sent = not testing

                _logger.info(f"Send Message ZNS successfully for Invoice {self.name}!")

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

    # /// PREPARING OPTIMIZE ///

    def _execute_send_message(self, ZNSConfiguration, payload):
        # Step 1: Validate Input
        if not ZNSConfiguration or not payload:
            _logger.error("Invalid ZNSConfiguration or payload.")
            return {"success": False, "error": "Invalid input"}

        # Step 2: Prepare Request Data
        url = ZNSConfiguration._get_sub_url_zns("/message/template")
        headers = ZNSConfiguration._get_headers()
        method = "POST"

        # Step 3: Execute Request
        try:
            response, response_data = self.env["zalo.log.request"].do_execute(
                url,
                method=method,
                headers=headers,
                payload=json.dumps(payload),
                is_check=True,
            )
        except Exception as e:
            _logger.error(f"An error occurred while sending the message: {e}")
            return {"success": False, "error": str(e)}

        # Step 4: Handle Response
        if response_data.get("error") != 0:
            error_message = response_data.get("message", "Unknown error")
            _logger.error(f"Failed to send message: {error_message}")
            return {"success": False, "error": error_message}

        # Step 5: Logging
        _logger.info(f"Message sent successfully: {response_data}")

        # Step 6: Return Result
        return {"success": True, "details": "Message sent successfully"}

    def _retrieve_zns_configuration(self):
        ZNSConfiguration = self.env["zalo.config"].search(
            [("primary_settings", "=", True)], limit=1
        )
        if not ZNSConfiguration:
            _logger.error("ZNS Configuration is not found!")
            return None
        return ZNSConfiguration

    def _prepare_payload(self, data):
        phone = convert_valid_phone_number(data.get("phone"))
        tracking_id = data.get("tracking_id")
        template_id = data.get("template_id")
        template_data = data.get("template_data")
        return ZNS_GET_PAYLOAD(
            phone, template_id, json.loads(template_data), tracking_id
        )

    def _send_message(self, zns_configuration, payload):
        response, datas = self.env["zalo.log.request"].do_execute(
            zns_configuration._get_sub_url_zns("/message/template"),
            method="POST",
            headers=zns_configuration._get_headers(),
            payload=json.dumps(payload),
            is_check=True,
        )
        return response, datas

    def _handle_response(self, datas, testing=False):
        # Check for errors in the response
        if datas and datas["error"] != 0:
            # Log the error message
            error_message = CODE_ERROR_ZNS.get(str(datas["error"]), "Unknown error")
            _logger.error(
                f"ZNS Code Error: {datas['error']}, Error Info: {error_message}"
            )
            return False
        else:
            # Log success message
            _logger.info(f"Send Message ZNS successfully for Invoice {self.name}!")
            if not testing:
                # Update relevant fields or perform actions to reflect the successful operation
                # For example, marking the message as sent in the database
                self.zns_notification_sent = True
                # Additional actions can be performed here

            return True
