# -*- coding: utf-8 -*-
import json
import logging

from odoo.addons.biz_zalo_common.models.common import (
    CODE_ERROR_ZNS,
    show_success_message,
)
from odoo.addons.mv_zalo.core.zalo_notification_service import (
    ZNS_GET_DATA_BY_TEMPLATE,
    ZNS_GET_PAYLOAD,
    zns_convert_valid_phonenumber,
)

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

CODE_ERROR_ZNS = dict(CODE_ERROR_ZNS)


class ZNSSendMessageTESTING(models.TransientModel):
    _name = "zns.send.message.testing.wizard"
    _description = _("Wizard: ZNS Send Message (TESTING)")

    template_id = fields.Many2one(
        string="ZNS Template",
        comodel_name="zns.template",
        domain="[('use_type', '!=', False)]",
    )
    template_preview_url = fields.Char(related="template_id.preview_url")
    model_testing = fields.Char(
        string="Model", compute="_compute_template_id", store=True
    )
    record_testing_id = fields.Integer(string="Record ID")
    phonenumber = fields.Char(
        string="Phone",
        default=lambda self: self.env["res.users"].browse(2).partner_id.phone or "",
    )
    data_send = fields.Text(
        string="Data Send", compute="_compute_data_send", store=True, readonly=False
    )

    @api.constrains("phonenumber")
    def _check_phonenumber_length(self):
        for wizard in self:
            if wizard.phonenumber and len(wizard.phonenumber) > 11:
                raise ValidationError(_("Phone number is invalid!"))

    @api.depends("template_id")
    def _compute_template_id(self):
        for wizard in self:
            if wizard.template_id:
                wizard.model_testing = wizard.template_id.use_type

    @api.depends("record_testing_id")
    def _compute_data_send(self):
        for wizard in self:
            if wizard.record_testing_id:
                # Use `sudo` to ensure record access
                model_name = wizard.model_testing or wizard.template_id.use_type
                record_testing = (
                    self.env[model_name].sudo().browse(wizard.record_testing_id)
                )
                if not record_testing.exists():
                    raise ValidationError(_("Record not found or deleted!"))

                data = {}
                for data_line in wizard.template_id.sample_data_ids:
                    data[data_line.name] = (
                        data_line.value
                        if not data_line.field_id
                        else ZNS_GET_DATA_BY_TEMPLATE(data_line, record_testing)
                    )

                wizard.data_send = json.dumps(data)

    def send_message(self):
        if not self.template_id:
            raise UserError(_("Please select a ZNS Template!"))

        if not self.template_id.sample_data_ids:
            raise UserError(_("Template does not have sample data!"))

        if not self.record_testing_id:
            raise UserError(_("Please input Record ID!"))

        if not self.phonenumber:
            raise UserError(_("Please input Phone Number!"))

        ZNSConfiguration = self._retrieve_zns_configuration()
        if not ZNSConfiguration:
            _logger.error("ZNS Configuration is not found!")
            return

        # Extract data
        phone = zns_convert_valid_phonenumber(self.phonenumber)
        template_id = self.template_id.template_id
        template_data = self.data_send
        tracking_id = self.record_testing_id

        # Execute ZNS request
        _, response_data = (
            self.env["zalo.log.request"]
            .sudo()
            .do_execute(
                ZNSConfiguration._get_sub_url_zns("/message/template"),
                method="POST",
                headers=ZNSConfiguration._get_headers(),
                payload=ZNS_GET_PAYLOAD(
                    phone, template_id, json.loads(template_data), tracking_id
                ),
                is_check=True,
            )
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
            return {
                "Warning": f"ZNS Code Error: {response_data['error']}, Error Info: {error_message}"
            }
        else:
            return show_success_message("Send Message ZNS successfully!")

    def _retrieve_zns_configuration(self):
        ZNSConfiguration = self.env["zalo.config"].search(
            [("primary_settings", "=", True)], limit=1
        )
        if not ZNSConfiguration:
            _logger.error("ZNS Configuration is not found!")
            return None
        return ZNSConfiguration
