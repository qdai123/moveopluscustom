# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request


class WebsiteHelpdesk(http.Controller):
    @http.route('/mv_website_helpdesk/helpdesk_ticket_lot_serial_number_scanned', type="json", auth="public")
    def scan_barcode(self, lot_serial_number):
        helpdesk_ticket = request.env["helpdesk.ticket"].sudo()
        if lot_serial_number:
            serial_numbers_fmt_list = helpdesk_ticket._format_portal_lot_serial_number(lot_serial_number)
            messages_list = helpdesk_ticket._validation_portal_lot_serial_number(serial_numbers_fmt_list)

            error_messages = [message[1] for message in messages_list if
                              message[0] in ["serial_number_is_empty",
                                             "serial_number_not_found",
                                             "serial_number_already_registered"]]
            if error_messages:
                return {"error": '\n'.join(error_messages)}
            else:
                return {"pass": "Data is ready!"}
        return {}
