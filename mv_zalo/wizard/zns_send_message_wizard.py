# -*- coding: utf-8 -*-
import json
import logging

from markupsafe import Markup
from odoo.addons.biz_zalo_common.models.common import (
    CODE_ERROR_ZNS,
    get_datetime,
    show_success_message,
)
from odoo.addons.mv_zalo.models.zns_templates import MODELS_ZNS_USE_TYPE

from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

CODE_ERROR_ZNS = dict(CODE_ERROR_ZNS)


class ZnsSendMessageWizard(models.TransientModel):
    _inherit = "zns.send.message.wizard"
    # TODO: Inherit ZnsSendMessageWizard and Optimization all of methods

    # === FIELDS ===#
    picking_id = fields.Many2one("stock.picking", readonly=True)
    move_id = fields.Many2one("stock.move", readonly=True)
    move_line_id = fields.Many2one("stock.move.line", readonly=True)
    account_move_id = fields.Many2one("account.move", readonly=True)
    account_move_line_id = fields.Many2one("account.move.line", readonly=True)

    # === Fields OVERRIDE ===#
    template_id = fields.Many2one(
        "zns.template",
        "ZNS Template",
        domain="[('use_type', '=', use_type)]",
        required=True,
    )
    use_type = fields.Selection(selection_add=MODELS_ZNS_USE_TYPE)

    # === OVERRIDE METHODS ===#

    @api.onchange("template_id")
    def onchange_template_id(self):  # FULL OVERRIDE
        if not self.template_id or not self.template_id.sample_data_ids:
            return

        use_type_mapping = {
            "sale.order": self.order_id,
            "loyalty.card": self.coupon_id,
            "stock.picking": self.picking_id,
            "account.move": self.account_move_id,
        }

        data = {}
        for sample_id in self.template_id.sample_data_ids:
            related_record = use_type_mapping.get(self.use_type)
            if related_record:
                data[sample_id.name] = (
                    sample_id.value
                    if not sample_id.field_id
                    else self._get_sample_data_by(sample_id, related_record)
                )

        self.template_data = json.dumps(data) if data else "{}"

    def generate_zns_history(self, data, config_id=False):  # FULL OVERRIDE
        zns_history_id = self.env["zns.history"].search(
            [("msg_id", "=", data.get("msg_id"))], limit=1
        )
        sent_time = (
            get_datetime(data.get("sent_time", False))
            if data.get("sent_time", False)
            else ""
        )

        if not zns_history_id:
            origin = None
            partner_id = False
            if self.use_type == "sale.order":
                origin = self.order_id.name if self.order_id else ""
                partner_id = (
                    self.order_id.partner_id.id
                    if self.order_id and self.order_id.partner_id
                    else False
                )
            elif self.use_type == "loyalty.card":
                origin = self.coupon_id.display_name if self.coupon_id else ""
                partner_id = (
                    self.coupon_id.partner_id.id
                    if self.coupon_id and self.coupon_id.partner_id
                    else False
                )
            elif self.use_type == "stock.picking":
                origin = self.picking_id.name if self.picking_id else ""
                partner_id = (
                    self.picking_id.sale_id.partner_id.id
                    if self.picking_id
                    and self.picking_id.sale_id
                    and self.picking_id.sale_id.partner_id
                    else False
                )
            elif self.use_type == "account.move":
                origin = self.account_move_id.name if self.account_move_id else ""
                partner_id = (
                    self.account_move_id.partner_id.id
                    if self.account_move_id and self.account_move_id.partner_id
                    else False
                )

            zns_history_id = zns_history_id.create(
                {
                    "msg_id": data.get("msg_id"),
                    "sent_time": sent_time,
                    "zalo_config_id": config_id and config_id.id or False,
                    "origin": origin,
                    "partner_id": partner_id,
                    "template_id": self.template_id and self.template_id.id or False,
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

    def send_email_action(self):  # FULL OVERRIDE
        try:
            config_id = self.env["zalo.config"].search(
                [("primary_settings", "=", True)], limit=1
            )
            if not config_id:
                raise ValidationError("Config not found!")

            LogRequest = self.env["zalo.log.request"]
            sub_url = "/message/template"
            url_api = config_id._get_sub_url_zns(sub_url)

            _, datas = LogRequest.do_execute(
                url_api,
                method="POST",
                is_check=True,
                headers=config_id._get_headers(),
                payload=self._get_payload(),
            )

            if (
                datas
                and datas.get("data", False)
                and datas.get("error") == 0
                and datas.get("message") == "Success"
            ):
                data = datas.get("data")
                if data:
                    self.process_data(data, config_id)
                return show_success_message("Send Message ZNS successfully!")
            else:
                error = "Code Error: %s, Error Info: %s" % (
                    datas["error"],
                    CODE_ERROR_ZNS.get(str(datas["error"])),
                )
                raise ValidationError(error)
        except Exception as e:
            _logger.error(f"Error in send_email_action: {str(e)}")

    # === MOVEOPLUS METHODS ===#

    @api.model
    def _zns_message_template(self, zns_message_id, zns_quota, sent_time):
        return (
            '<p class="mb-0">Đã gửi tin nhắn ZNS</p>'
            + """
            <ul class="o_Message_trackingValues mb-0 ps-4">
                <li>
                    <div class="o_TrackingValue d-flex align-items-center flex-wrap mb-1" role="group">
                        <span class="o_TrackingValue_oldValue me-1 px-1 text-muted fw-bold">ID thông báo ZNS: </span>
                        <span class="o_TrackingValue_newValue me-1 fw-bold text-info">{zns_message_id}</span>
                    </div>
                </li>
                <li>
                    <div class="o_TrackingValue d-flex align-items-center flex-wrap mb-1" role="group">
                        <span class="o_TrackingValue_oldValue me-1 px-1 text-muted fw-bold">Thời gian gửi thông báo ZNS: </span>
                        <span class="o_TrackingValue_newValue me-1 fw-bold text-info">{sent_time}</span>
                    </div>
                </li>
                <li>
                    <div class="o_TrackingValue d-flex align-items-center flex-wrap mb-1" role="group">
                        <span class="o_TrackingValue_oldValue me-1 px-1 text-muted fw-bold">Thông tin quota thông báo ZNS của OA: </span>
                        <span class="o_TrackingValue_newValue me-1 fw-bold text-info">{zns_quota}</span>
                    </div>
                </li>
            </ul>""".format(
                zns_message_id=zns_message_id, sent_time=sent_time, zns_quota=zns_quota
            )
        )

    def generate_zns_message(self, data, sent_time):
        return self._zns_message_template(
            data.get("msg_id"), sent_time, data.get("quota")
        )

    # /// BUSINESS METHODS ///

    def process_data(self, data, config_id):
        if self.use_type in ["sale.order", "stock.picking", "account.move"]:
            sent_time = (
                get_datetime(data.get("sent_time", False))
                if data.get("sent_time", False)
                else ""
            )
            sent_time = sent_time and self.get_tz_user(sent_time) or ""

            msg = self.generate_zns_message(data, sent_time)
            self.generate_zns_history(data, config_id)
            if self.use_type == "sale.order":
                self.order_id.message_post(body=Markup(msg))
            elif self.use_type == "stock.picking":
                self.picking_id.message_post(body=Markup(msg))
            elif self.use_type == "account.move":
                self.account_move_id.message_post(body=Markup(msg))
        elif self.use_type == "loyalty.card":
            self.generate_zns_history(data, config_id)
