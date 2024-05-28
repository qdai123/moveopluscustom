# -*- coding: utf-8 -*-
import json
import logging
import requests
import re

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

from markupsafe import Markup

from odoo import http, _
from odoo.http import request, Response
from odoo.addons.phone_validation.tools import phone_validation
from odoo.addons.website.controllers import form
from odoo.exceptions import ValidationError
from odoo.osv import expression

from werkzeug.utils import redirect
from werkzeug.exceptions import HTTPException, BadRequest

_logger = logging.getLogger(__name__)

# Groups Access:
PUBLIC_USER = "base.group_public"
PORTAL_USER = "base.group_portal"
INTERNAL_USER = "base.group_user"

# Templates Website Helpdesk:
HELPDESK_WARRANTY_ACTIVATION_FORM = (
    "mv_website_helpdesk.mv_helpdesk_warranty_activation_template"
)

# Ticket Type Codes for Warranty Activation:
SUB_DEALER_CODE = "kich_hoat_bao_hanh_dai_ly"
END_USER_CODE = "kich_hoat_bao_hanh_nguoi_dung_cuoi"

PARTNER_NOT_FOUND_ERROR = {"partner_not_found": True}
IS_NOT_AGENCY = "is_not_agency"
IS_EMPTY = "is_empty"
CODE_NOT_FOUND = "code_not_found"
CODE_ALREADY_REGISTERED = "code_already_registered"


class MVWebsiteHelpdesk(http.Controller):

    @http.route("/kich-hoat-bao-hanh", type="http", auth="public", website=True)
    def website_helpdesk_warranty_activation_teams(self, **kwargs):
        WarrantyActivationTeam = (
            request.env["helpdesk.team"]
            .sudo()
            .search([("use_website_helpdesk_warranty_activation", "=", True)], limit=1)
        )

        HelpdeskTicketType = request.env["helpdesk.ticket.type"]
        domain_ticket_type_obj = [
            ("user_for_warranty_activation", "=", True),
            ("code", "in", [SUB_DEALER_CODE, END_USER_CODE]),
        ]

        # Defining ticket type for Warranty Activation for Sub-Dealer and End-User:
        type_sub_dealer = HelpdeskTicketType.sudo().search(
            [
                ("user_for_warranty_activation", "=", True),
                ("code", "=", SUB_DEALER_CODE),
            ],
            limit=1,
        )
        type_end_user = HelpdeskTicketType.sudo().search(
            [
                ("user_for_warranty_activation", "=", True),
                ("code", "=", END_USER_CODE),
            ],
            limit=1,
        )

        return http.request.render(
            HELPDESK_WARRANTY_ACTIVATION_FORM,
            {
                "anonymous": self._is_anonymous(),
                "default_helpdesk_team": WarrantyActivationTeam,
                "ticket_type_objects": HelpdeskTicketType.sudo().search(
                    domain_ticket_type_obj, order="id"
                ),
                "type_is_sub_dealer_id": type_sub_dealer.id or False,
                "type_is_end_user_id": type_end_user.id or False,
            },
        )

    @http.route("/mv_website_helpdesk/check_partner_phone", type="json", auth="public")
    def check_partner_phonenumber(self, phone_number):
        try:
            partner_info = (
                request.env["res.partner"]
                .sudo()
                .search(
                    ["|", ("phone", "=", phone_number), ("mobile", "=", phone_number)],
                    limit=1,
                )
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

    @http.route("/mv_website_helpdesk/check_scanned_code", type="json", auth="public")
    def check_scanned_code(
        self,
        codes,
        ticket_type,
        partner_email,
        by_pass_check_partner_agency,
        tel_activation,
    ):
        Ticket = request.env["helpdesk.ticket"].sudo()
        error_messages = []

        if ticket_type:
            ticket_type = (
                request.env["helpdesk.ticket.type"].sudo().browse(int(ticket_type))
            )
            _logger.debug(f"Ticket Type: {ticket_type}")

        partner = False
        if partner_email and self.is_valid_email(partner_email):
            partner = (
                request.env["res.partner"]
                .sudo()
                .search([("email", "=", partner_email)], limit=1)
            )
            if not by_pass_check_partner_agency and partner and not partner.is_agency:
                _logger.debug(
                    f"{IS_NOT_AGENCY}: Bạn không phải là Đại lý của Moveo Plus.Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin."
                )
                # error_messages.append(
                #     (
                #         IS_NOT_AGENCY,
                #         "Bạn không phải là Đại lý của Moveo Plus."
                #         "Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin.",
                #     )
                # )
                # return error_messages

        if tel_activation:
            _logger.debug(f"Tel Activation: {tel_activation}")

        # [!] ===== Validate empty codes =====
        if not codes:
            error_messages.append(
                (
                    IS_EMPTY,
                    "Vui lòng nhập vào Số lô/Mã vạch hoặc mã QR-Code để kiểm tra!",
                )
            )
            return error_messages

        # Convert to list of codes
        codes_converted = Ticket.convert_to_list_codes(codes)
        codes_val = list(set(codes_converted)) if codes_converted else []

        valid_qr_code = Ticket._validate_qr_code(codes_val)
        valid_lot_serial_number = Ticket._validate_lot_serial_number(codes_val)

        # [!] ===== Validate codes are not found on system =====
        if not valid_qr_code and not valid_lot_serial_number:
            error_messages.append(
                (
                    CODE_NOT_FOUND,
                    f"Mã {', '.join(codes_val) if len(codes_val) > 1 else codes_val[0]} không tồn tại trên hệ thống hoặc chưa cập nhật.",
                )
            )

        # [!] ===== Validate codes has been registered on other tickets =====
        qrcodes = list(set(valid_qr_code.mapped("qr_code")))
        serial_numbers = list(set(valid_lot_serial_number.mapped("lot_name")))

        # QR-Codes VALIDATION
        if qrcodes:
            self._validate_codes(
                qrcodes, ticket_type, partner, error_messages, "qr_code"
            )

        # Lot/Serial Number VALIDATION
        if serial_numbers:
            self._validate_codes(
                serial_numbers, ticket_type, partner, error_messages, "lot_name"
            )

        # Convert the set back to a list
        error_messages = list(set(error_messages))

        return error_messages

    def _validate_codes(self, codes, ticket_type, partner, error_messages, field_name):
        TicketProductMoves = request.env["mv.helpdesk.ticket.product.moves"].sudo()

        for code in codes:
            conflicting_ticket_sub_dealer = TicketProductMoves.search(
                self._get_domain(SUB_DEALER_CODE, code, field_name), limit=1
            )
            conflicting_ticket_end_user = TicketProductMoves.search(
                self._get_domain(END_USER_CODE, code, field_name), limit=1
            )

            if (
                len(conflicting_ticket_sub_dealer) > 0
                and len(conflicting_ticket_end_user) > 0
            ):
                message = (
                    f"Mã {code} đã trùng với Tickets khác có mã là "
                    f"(#{conflicting_ticket_sub_dealer.helpdesk_ticket_id.id}, "
                    f"#{conflicting_ticket_end_user.helpdesk_ticket_id.id})."
                )
                error_messages.append((CODE_ALREADY_REGISTERED, message))
            else:
                if ticket_type.code in [SUB_DEALER_CODE, END_USER_CODE]:
                    self._handle_code(
                        conflicting_ticket_sub_dealer,
                        conflicting_ticket_end_user,
                        code,
                        partner,
                        error_messages,
                        ticket_type.code,
                    )

    def _get_domain(self, ticket_type_code, code, field_name):
        return [
            ("helpdesk_ticket_id", "!=", False),
            ("helpdesk_ticket_type_id.code", "=", ticket_type_code),
            (f"stock_move_line_id.{field_name}", "=", code),
        ]

    def _handle_code(
        self,
        conflicting_ticket_sub_dealer,
        conflicting_ticket_end_user,
        code,
        partner,
        error_messages,
        ticket_type_code,
    ):
        validate_different_partner_for_sub = (
            len(conflicting_ticket_sub_dealer) > 0
            and conflicting_ticket_sub_dealer.partner_id.id != partner.id
        )
        validate_different_partner_for_end = (
            len(conflicting_ticket_end_user) > 0
            and conflicting_ticket_end_user.partner_id.id != partner.id
        )
        # Validate if the code is already registered on other tickets by different Partners
        if validate_different_partner_for_sub or validate_different_partner_for_end:
            if self._is_anonymous():
                message = f"Mã {code} đã được đăng ký cho đơn vị khác!"
            else:
                conflicting_ticket = (
                    conflicting_ticket_sub_dealer
                    if validate_different_partner_for_sub
                    else conflicting_ticket_end_user
                )
                message = (
                    f"Mã {code} đã được đăng ký cho đơn vị khác, "
                    f"phiếu có mã là (#{conflicting_ticket.helpdesk_ticket_id.id})."
                )
            error_messages.append((CODE_ALREADY_REGISTERED, message))
        # Validate if the code is already registered on other tickets with specific ticket type by current Partner
        else:
            conflicting_ticket = (
                conflicting_ticket_sub_dealer
                if ticket_type_code == SUB_DEALER_CODE
                else conflicting_ticket_end_user
            )
            if len(conflicting_ticket) > 0:
                if self._is_anonymous():
                    message = f"Mã {code} đã trùng với Ticket khác!"
                else:
                    message = (
                        f"Mã {code} đã trùng với Ticket khác, "
                        f"phiếu có mã là (#{conflicting_ticket.helpdesk_ticket_id.id})."
                    )
                error_messages.append((CODE_ALREADY_REGISTERED, message))

    # =================================
    # HELPER / PRIVATE Methods
    # =================================

    def is_valid_email(self, email):
        """
        Check if the input string is a valid email address.

        Args:
            email (str): The email address to validate.

        Returns:
            bool: True if the email address is valid, False otherwise.
        """
        regex = r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)"
        return re.search(regex, email) is not None

    def _is_anonymous(self):
        """
        Check if the user is anonymous or public user.
        :return: True if the user is anonymous, False otherwise.
        """
        user = request.env.user
        is_public_user = user == request.env.ref("base.public_user")
        is_not_portal_or_internal_user = not user.has_group(
            PORTAL_USER
        ) and not user.has_group(INTERNAL_USER)

        return is_public_user and is_not_portal_or_internal_user


class WebsiteForm(form.WebsiteForm):

    # =============== MOVEOPLUS Override ===============
    def _handle_website_form(self, model_name, **kwargs):
        """
        Handle the website form submission. If the model is 'helpdesk.ticket' and a team_id is provided,
        it checks if the team uses the website helpdesk warranty activation. If so, it fetches the partner
        based on the provided email and sets the partner_id in the request parameters.

        Args:
            model_name (str): The name of the model.
            **kwargs: Additional keyword arguments.

        Returns:
            The result of the parent method call.
        """
        model = model_name or request.params.get("model_name")
        team_id = request.params.get("team_id")

        if model == "helpdesk.ticket" and team_id:
            self._handle_helpdesk_ticket_form(team_id)

        return super(WebsiteForm, self)._handle_website_form(model_name, **kwargs)

    def _handle_helpdesk_ticket_form(self, team_id):
        """
        Handle the form submission for 'helpdesk.ticket'. If the team uses the website helpdesk warranty activation,
        it fetches the partner based on the provided email and sets the partner_id in the request parameters.

        Args:
            team_id (int): The ID of the helpdesk team.
        """
        team = request.env["helpdesk.team"].sudo().browse(int(team_id))

        if team and team.use_website_helpdesk_warranty_activation:
            email = request.params.get("partner_email")

            if email:
                partner = self._get_partner_by_email(email)

                if not partner:
                    return json.dumps({"error": _("Partner not found!")})
                else:
                    request.params["partner_id"] = partner.id

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
