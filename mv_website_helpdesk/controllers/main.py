# -*- coding: utf-8 -*-
import json
import logging
import requests

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

from markupsafe import Markup

from odoo import http, _
from odoo.http import request, Response
from odoo.addons.phone_validation.tools import phone_validation
from odoo.exceptions import ValidationError
from odoo.addons.website.controllers import form

from werkzeug.utils import redirect
from werkzeug.exceptions import HTTPException, BadRequest

_logger = logging.getLogger(__name__)

# BASE Templates Website Helpdesk:
HELPDESK_WARRANTY_ACTIVATION_FORM = (
    "mv_website_helpdesk.mv_helpdesk_warranty_activation_template"
)

# BASE Groups Access:
PORTAL_USER = "base.group_portal"
INTERNAL_USER = "base.group_user"

PARTNER_NOT_FOUND_ERROR = {"partner_not_found": True}
ERROR_MESSAGES = {
    "EMPTY_CODES": "Vui lòng nhập vào Số lô/Mã vạch hoặc mã QR-Code để kiểm tra!",
    "CODE_NOT_FOUND": "Mã {code} không tồn tại trên hệ thống hoặc chưa cập nhật. \nVui lòng kiểm tra lại.",
    "CODE_ALREADY_REGISTERED": "Mã {code} đã trùng với Ticket khác mã là (#{ticket_id}).\nVui lòng chọn một mã khác.",
}


class MVWebsiteHelpdesk(http.Controller):

    @http.route(
        "/kich-hoat-bao-hanh",
        type="http",
        auth="public",
        website=True,
        csrf=False,
        save_session=False,
    )
    def warranty_activation_form_public(self, **kwargs):
        HelpdeskTeam = request.env["helpdesk.team"]
        HelpdeskTicketType = request.env["helpdesk.ticket.type"]
        ref = request.env.ref

        team_id = HelpdeskTeam.sudo().search(
            [("use_website_helpdesk_warranty_activation", "=", True)], limit=1
        )
        ticket_type_objects = HelpdeskTicketType.sudo().search(
            [
                (
                    "id",
                    "in",
                    [
                        ref("mv_helpdesk.type_guarantee_activation_for_sub_dealer").id
                        or False,
                        ref("mv_helpdesk.type_guarantee_activation_for_end_user").id
                        or False,
                    ],
                ),
            ],
            order="id",
        )

        values = {
            "anonymous": self._is_anonymous(),
            "default_helpdesk_team": team_id,
            "ticket_type_objects": ticket_type_objects,
            "type_is_sub_dealer_id": ref(
                "mv_helpdesk.type_guarantee_activation_for_sub_dealer"
            ).id
            or False,
            "type_is_end_user_id": ref(
                "mv_helpdesk.type_guarantee_activation_for_end_user"
            ).id
            or False,
        }

        template = http.request.render(HELPDESK_WARRANTY_ACTIVATION_FORM, values)

        # TODO: Remove these "print" after fixed
        _logger.debug(
            f"######### Request Session Headers: {requests.Session().headers}"
        )
        _logger.debug(f"######### Request Cookies: {request.httprequest.cookies}")

        return template

    @http.route(
        "/mv_website_helpdesk/validate_partner_phonenumber", type="json", auth="public"
    )
    def validate_partner_phonenumber(self, phone_number):
        """
        Validates the phone number and fetches the partner's information based on the phone number.

        Args:
            phone_number (str): The phone number of the partner.

        Returns:
            dict: A dictionary containing the partner's information if found, else a dictionary indicating that the partner was not found.
        """
        try:
            Partner = request.env["res.partner"].sudo()

            partner_info = Partner.search(
                ["|", ("phone", "=", phone_number), ("mobile", "=", phone_number)],
                limit=1,
            )

            if not partner_info:
                return PARTNER_NOT_FOUND_ERROR

            return {
                "partner_id": partner_info.id,
                "partner_name": partner_info.name,
                "partner_email": partner_info.email,
            }
        except Exception as e:
            _logger.error("Failed to validate partner phone number: %s", e)
            return PARTNER_NOT_FOUND_ERROR

    @http.route(
        "/mv_website_helpdesk/validate_scanned_code", type="json", auth="public"
    )
    def validate_scanned_code(self, codes):
        """
        Validates the scanned codes. It checks if the codes are QR codes, and if they are, it validates them against the existing codes in the system.
        If the codes are not QR codes, it validates them as lot names. It also checks if the codes are already registered in existing tickets.

        Args:
            codes (list): The list of codes to validate.

        Returns:
            list: A list of tuples containing the validation results for each code.
        """
        messages_list = []
        ticket_product_moves_env = request.env[
            "mv.helpdesk.ticket.product.moves"
        ].sudo()
        move_line_env = request.env["stock.move.line"].sudo()

        if not codes:
            messages_list.append(("is_empty", ERROR_MESSAGES["EMPTY_CODES"]))
            return messages_list

        is_qrcode = self._is_qrcode(codes)
        if is_qrcode:
            list_codes = is_qrcode
            existing_codes = move_line_env.search(
                [("qr_code", "in", list_codes)]
            ).mapped("qr_code")
            domain_search = [("qr_code", "in", list_codes)]
        else:
            list_codes = codes
            existing_codes = move_line_env.search(
                [("lot_name", "in", list_codes)]
            ).mapped("lot_name")
            domain_search = [("lot_name", "in", existing_codes)]

        existing_tickets = ticket_product_moves_env.search(domain_search)

        for code in list_codes:
            if code not in existing_codes:
                messages_list.append(
                    (
                        "code_not_found",
                        ERROR_MESSAGES["CODE_NOT_FOUND"].format(code=code),
                    )
                )
            else:
                if is_qrcode:
                    conflicting_ticket = existing_tickets.filtered(
                        lambda r: r.stock_move_line_id.qr_code == code
                        and r.helpdesk_ticket_id
                    )
                else:
                    conflicting_ticket = existing_tickets.filtered(
                        lambda r: r.lot_name == code and r.helpdesk_ticket_id
                    )

                if conflicting_ticket:
                    ticket_id = (
                        conflicting_ticket.helpdesk_ticket_id
                        and conflicting_ticket.helpdesk_ticket_id.id
                        or False
                    )
                    messages_list.append(
                        (
                            "code_already_registered",
                            ERROR_MESSAGES["CODE_ALREADY_REGISTERED"].format(
                                code=code, ticket_id=ticket_id
                            ),
                        )
                    )
                else:
                    if is_qrcode:
                        move_line = move_line_env.search(
                            [("qr_code", "=", code)], limit=1
                        )
                    else:
                        move_line = move_line_env.search(
                            [("lot_name", "=", code)], limit=1
                        )

                    if move_line:
                        if is_qrcode:
                            messages_list.append(
                                (
                                    move_line.qr_code,
                                    f"{move_line.product_id.name if move_line.product_id else ''}",
                                )
                            )
                        else:
                            messages_list.append(
                                (
                                    move_line.lot_name,
                                    f"{move_line.product_id.name if move_line.product_id else ''}",
                                )
                            )

        return messages_list

    # =================================
    # HELPER/PRIVATE Methods
    # =================================

    def _is_qrcode(self, codes):
        if not codes:
            return False

        move_line_env = request.env["stock.move.line"].sudo()
        return move_line_env.search(
            [("qr_code", "in", codes), ("inventory_period_id", "!=", False)]
        ).mapped("qr_code")

    def _is_anonymous(self):
        """
        Check if the user is anonymous.
        :return: True if the user is anonymous, False otherwise.
        """
        user = request.env.user
        return not user.has_group(PORTAL_USER) and not user.has_group(INTERNAL_USER)


class WebsiteForm(form.WebsiteForm):

    # =============== MOVEOPLUS Override ===============
    def _handle_website_form(self, model_name, **kwargs):
        """
        Handles the form submission on the website. It checks if the model is 'helpdesk.ticket'
        and if the helpdesk team uses the website helpdesk warranty activation. If these conditions
        are met, it validates the partner email and the portal lot/serial number.

        Args:
            model_name (str): The name of the model.
            **kwargs: Variable length argument list.

        Returns:
            json: A JSON object containing the result of the form submission.
        """
        try:
            model = model_name or request.params.get("model_name")
            team_id = request.params.get("team_id")
            if model == "helpdesk.ticket" and team_id:
                HelpdeskTeam = request.env["helpdesk.team"].sudo().browse(int(team_id))
                if (
                    HelpdeskTeam
                    and HelpdeskTeam.use_website_helpdesk_warranty_activation
                ):
                    email = request.params.get("partner_email")
                    if email:
                        partner = self._get_partner_by_email(email)
                        if not partner:
                            return json.dumps({"error": _(_("Partner not found!"))})
                        else:
                            request.params["partner_id"] = partner.id

                    codes = request.params.get("portal_lot_serial_number")
                    if codes:
                        tickets_by_codes = (
                            request.env["helpdesk.ticket"]
                            .sudo()
                            ._validation_portal_lot_serial_number(codes)
                        )
                        if tickets_by_codes:
                            for ticket in tickets_by_codes:
                                if ticket[0] in [
                                    "code_not_found",
                                    "code_already_registered",
                                ]:
                                    return json.dumps({"error": _(ticket[1])})

            return super(WebsiteForm, self)._handle_website_form(model_name, **kwargs)
        except Exception as e:
            _logger.error("Failed to handle website form: %s", e)
            pass

    def _get_partner_by_email(self, email):
        """
        Fetches the partner by email.

        Args:
            email (str): The email of the partner.

        Returns:
            recordset: A recordset of the partner.
        """
        if request.env.user.email == email:
            return request.env.user.partner_id
        else:
            return (
                request.env["res.partner"]
                .sudo()
                .search([("email", "=", email)], limit=1)
            )
