# -*- coding: utf-8 -*-
try:
    import phonenumbers
except ImportError:
    phonenumbers = None

from odoo import http, _
from odoo.http import request
from odoo.addons.account.models.company import PEPPOL_LIST


class WebsiteHelpdesk(http.Controller):
    @http.route(
        "/mv_website_helpdesk/helpdesk_ticket_lot_serial_number_scanned",
        type="json",
        auth="public",
    )
    def scan_barcode(self, lot_serial_number):
        helpdesk_ticket = request.env["helpdesk.ticket"].sudo()
        if lot_serial_number:
            serial_numbers_fmt_list = helpdesk_ticket._format_portal_lot_serial_number(
                lot_serial_number
            )
            messages_list = helpdesk_ticket._validation_portal_lot_serial_number(
                serial_numbers_fmt_list
            )

            error_messages = [
                message[1]
                for message in messages_list
                if message[0]
                in [
                    "serial_number_is_empty",
                    "serial_number_not_found",
                    "serial_number_already_registered",
                ]
            ]
            if error_messages:
                return {"error": "\n".join(error_messages)}
            else:
                return {"pass": "Data is ready!"}
        return {}

    @http.route(
        "/mv_website_helpdesk/check_partner_phone_number", type="json", auth="public"
    )
    def check_partner_phone_number(self, phone_number):
        response = {}

        # try:
        #     phone_nbr = phonenumbers.parse(phone_number, None)
        # except phonenumbers.phonenumberutil.NumberParseException:
        #     response.update({"number_parse_exception_failed": True})
        #     return response

        # if not phonenumbers.is_valid_number(phone_nbr):
        #     response.update({"invalid_phone_number": True})
        #     return response

        # country_code = phonenumbers.phonenumberutil.region_code_for_number(phone_nbr)
        # if country_code not in PEPPOL_LIST:
        #     response.update({"countries_support": True})
        #     return response

        domain = ["|", ("phone", "=", phone_number), ("mobile", "=", phone_number)]
        partner_info = http.request.env["res.partner"].sudo().search(domain, limit=1)

        if not partner_info:
            response.update({"partner_not_found": True})
            return response

        response = {
            "partner_id": partner_info[0].id,
            "partner_name": partner_info[0].name,
            "partner_email": partner_info[0].email,
        }
        return response
