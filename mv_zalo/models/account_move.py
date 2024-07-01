# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

from odoo.addons.biz_zalo_common.models.common import convert_valid_phone_number

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # === FIELDS ===#
    zns_notification_sent = fields.Boolean("ZNS Notification Sent", default=False)

    # === MOVEOPLUS METHODS ===#

    # /// CRON JOB ///
    @api.model
    def _cron_notification_date_due_journal_entry(
        self, dates_before=False, phone_number=False
    ):
        div_dates = 2 if not dates_before else dates_before
        print(div_dates)

        if phone_number:
            valid_phone_number = convert_valid_phone_number(phone_number)
            print(valid_phone_number)

        _logger.info("Cron Job: Notification Date Due Journal Entry")

        return True
