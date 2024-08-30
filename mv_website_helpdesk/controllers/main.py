# -*- coding: utf-8 -*-
import json
import logging
import re

import pytz

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

from odoo import http, _, fields
from odoo.addons.website.controllers import form
from odoo.http import request
from odoo.osv import expression
from datetime import datetime
from odoo.addons.mv_helpdesk.models.helpdesk_ticket import (
    END_USER_CODE,
    SUB_DEALER_CODE,
)
from werkzeug.exceptions import NotFound

_logger = logging.getLogger(__name__)

# Groups Access:
PUBLIC_USER = "base.group_public"
PORTAL_USER = "base.group_portal"
INTERNAL_USER = "base.group_user"

PARTNER_NOT_FOUND_ERROR = {"partner_not_found": True}
IS_NOT_AGENCY = "is_not_agency"
IS_EMPTY = "is_empty"
CODE_NOT_FOUND = "code_not_found"
CODE_ALREADY_REGISTERED = "code_already_registered"

# Helpdesk Activation Warranty Form and Team:
HELPDESK_ACTIVATION_WARRANTY_FORM = (
    "mv_website_helpdesk.mv_helpdesk_warranty_activation_template"
)
HELPDESK_ACTIVATION_WARRANTY_TEAM = (
    "mv_website_helpdesk.mv_website_helpdesk_helpdesk_team_warranty_activation_form"
)

# Helpdesk Claim Warranty Form and Team:
HELPDESK_CLAIM_WARRANTY_ACTIVATION_FORM = (
    "mv_website_helpdesk.mv_claim_warranty_template"
)
HELPDESK_CLAIM_WARRANTY_TEAM = "mv_website_helpdesk.mv_helpdesk_claim_warranty"


class MVWebsiteHelpdesk(http.Controller):

    @http.route("/claim-bao-hanh", type="http", auth="public", website=True)
    def website_helpdesk_claim_warranty(self, **kwargs):
        _logger.debug(f"Method [website_helpdesk_claim_warranty] Params: {kwargs}")

        helpdesk_claim_team = request.env.ref(HELPDESK_CLAIM_WARRANTY_TEAM)
        teams_domain = [("use_website_helpdesk_warranty_activation", "=", True)]
        if not request.env.user.has_group("helpdesk.group_helpdesk_manager"):
            teams_domain = expression.AND(
                [
                    teams_domain,
                    [
                        ("website_published", "=", True),
                        ("id", "=", helpdesk_claim_team.id),
                    ],
                ]
            )

        warranty_teams = (
            request.env["helpdesk.team"].sudo().search(teams_domain, order="id asc")
        )
        if not warranty_teams:
            raise NotFound()

        # === FETCH Ticket Types === #
        WarrantyType = (
            request.env["helpdesk.ticket.type"]
            .sudo()
            .search([("code", "=", "yeu_cau_bao_hanh")], limit=1)
        )

        result = {
            "helpdesk_team": "claim_warranty",
            "default_helpdesk_team": warranty_teams,
            "team": warranty_teams[0],
            "multiple_teams": len(warranty_teams) > 1,
            "ticket_type_objects": WarrantyType,
        }
        return request.render(HELPDESK_CLAIM_WARRANTY_ACTIVATION_FORM, result)

    @http.route("/kich-hoat-bao-hanh", type="http", auth="public", website=True)
    def website_helpdesk_activation_warranty(self, **kwargs):
        _logger.debug(f"Method [website_helpdesk_activation_warranty] Params: {kwargs}")

        helpdesk_activation_team = request.env.ref(HELPDESK_ACTIVATION_WARRANTY_TEAM)
        teams_domain = [("use_website_helpdesk_warranty_activation", "=", True)]
        if not request.env.user.has_group("helpdesk.group_helpdesk_manager"):
            teams_domain = expression.AND(
                [
                    teams_domain,
                    [
                        ("website_published", "=", True),
                        ("id", "=", helpdesk_activation_team.id),
                    ],
                ]
            )

        warranty_teams = (
            request.env["helpdesk.team"].sudo().search(teams_domain, order="id asc")
        )
        if not warranty_teams:
            raise NotFound()

        # === FETCH Ticket Types === #
        ticket_types = (
            request.env["helpdesk.ticket.type"]
            .sudo()
            .search([("user_for_warranty_activation", "=", True)], order="id asc")
        )
        SubDealer = ticket_types.filtered(lambda t: t.code == SUB_DEALER_CODE)
        EndUser = ticket_types.filtered(lambda t: t.code == END_USER_CODE)

        result = {
            "helpdesk_team": "activation_warranty",
            "default_helpdesk_team": warranty_teams,
            "team": warranty_teams[0],
            "multiple_teams": len(warranty_teams) > 1,
            "ticket_type_objects": ticket_types,
            "type_is_sub_dealer_id": (SubDealer.id if SubDealer else False),
            "type_is_end_user_id": EndUser.id if EndUser else False,
            "anonymous": self._is_anonymous(),
        }
        return request.render(HELPDESK_ACTIVATION_WARRANTY_FORM, result)

    # =================================
    # VALIDATION Methods
    # =================================

    @http.route("/helpdesk/check_partner_phone", type="json", auth="public")
    def check_partner_phonenumber(self, phone_number):
        try:
            partner = self._search_partner_by_phone(phone_number)
            if not partner:
                return PARTNER_NOT_FOUND_ERROR

            return {
                "partner_id": partner.id,
                "partner_name": partner.name,
                "partner_email": partner.email,
            }
        except Exception as e:
            _logger.error(
                "Failed to validate partner phone number: %s", e, exc_info=True
            )
            return PARTNER_NOT_FOUND_ERROR

    def _search_partner_by_phone(self, phone_number):
        return (
            request.env["res.partner"]
            .sudo()
            .search(
                ["|", ("phone", "=", phone_number), ("mobile", "=", phone_number)],
                limit=1,
            )
        )

    @http.route("/helpdesk/check_scanned_code", type="json", auth="public")
    def check_scanned_code(self, codes, **kwargs):
        session_info = request.env["ir.http"].session_info()
        _logger.debug(f"Session Info: {session_info}")

        error_messages = []
        ticket_type = kwargs.get("ticket_type")
        ticket_type_id = int(ticket_type)
        partner_name = kwargs.get("partner_name")
        partner_email = kwargs.get("partner_email")
        tel_activation = kwargs.get("tel_activation")
        by_pass_check = kwargs.get("by_pass_check") or False

        TicketType = request.env["helpdesk.ticket.type"].sudo().browse(ticket_type_id)
        if not TicketType:
            raise NotFound()

        partner = False
        if partner_email and self.is_valid_email(partner_email):
            partner = (
                request.env["res.partner"]
                .sudo()
                .search(
                    [
                        ("name", "=", partner_name),
                        ("email", "=", partner_email),
                    ],
                    limit=1,
                )
            )
            is_partner_agency = bool(
                request.env["res.partner"].sudo().browse(partner.id).is_agency
            )
            is_partner_has_parent_agency = bool(
                request.env["res.partner"].sudo().browse(partner.id).parent_id.is_agency
            )
            if (
                not by_pass_check
                and not is_partner_agency
                and not is_partner_has_parent_agency
            ):
                error_messages.append(
                    (
                        IS_NOT_AGENCY,
                        "Bạn không phải là Đại lý của Moveo Plus."
                        "Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin.",
                    )
                )
                return error_messages

        if tel_activation:
            _logger.debug(f"Tel Activation: {tel_activation}")

        # [!] ===== Validate empty codes =====
        if not codes:
            message_err = "Vui lòng nhập vào Số lô/Mã vạch hoặc mã QR-Code để kiểm tra!"
            error_messages.append((IS_EMPTY, message_err))
            return error_messages

        # Convert to list of codes
        codes_converted = (
            request.env["helpdesk.ticket"].sudo().convert_to_list_codes(codes)
        )
        codes_val = list(set(codes_converted)) if codes_converted else []

        # Validate codes
        valid_qr_code = (
            request.env["helpdesk.ticket"].sudo()._validate_qr_code(codes_val)
        )
        valid_lot_serial_number = (
            request.env["helpdesk.ticket"].sudo()._validate_lot_serial_number(codes_val)
        )

        # [!] ===== Validate codes are not found on system =====
        if not valid_qr_code and not valid_lot_serial_number:
            message_err = (
                f"Mã {', '.join(codes_val) if len(codes_val) > 1 else codes_val[0]} "
                f"không tồn tại trên hệ thống hoặc chưa cập nhật."
            )
            error_messages.append((CODE_NOT_FOUND, message_err))

        # [!] ===== Validate codes has been registered on other tickets =====
        qrcodes = list(set(valid_qr_code.mapped("qr_code")))
        serial_numbers = list(set(valid_lot_serial_number.mapped("lot_name")))

        # QR-Codes VALIDATION
        if not by_pass_check and qrcodes:
            self._validate_codes(
                error_messages=error_messages,
                field_name="ref",
                codes=qrcodes,
                ticket_type=TicketType,
                partner=partner,
            )

        # Lot/Serial Number VALIDATION
        if not by_pass_check and serial_numbers:
            self._validate_codes(
                error_messages=error_messages,
                field_name="name",
                codes=serial_numbers,
                ticket_type=TicketType,
                partner=partner,
            )

        # Convert the set back to a list
        error_messages = list(set(error_messages))

        if not by_pass_check:
            return error_messages
        else:
            code_input = []
            if len(qrcodes) > 0:
                code_input = qrcodes[0]
            elif len(serial_numbers) > 0:
                code_input = serial_numbers[0]

            filtered_error_messages = (
                list(
                    filter(
                        lambda item: item[0] != CODE_ALREADY_REGISTERED, error_messages
                    )
                )
                if len(error_messages) > 0
                else []
            )

            return (
                code_input if not filtered_error_messages else filtered_error_messages
            )

    def _validate_codes(self, error_messages, field_name, **kwargs):
        model_search = "mv.helpdesk.ticket.product.moves"
        codes = kwargs.get("codes")
        ticketType = kwargs.get("ticket_type")
        partner = kwargs.get("partner")

        for code in codes:
            conflicting_ticket_sub_dealer = (
                request.env[model_search]
                .sudo()
                .search(self._get_domain(SUB_DEALER_CODE, code, field_name), limit=1)
            )
            conflicting_ticket_end_user = (
                request.env[model_search]
                .sudo()
                .search(self._get_domain(END_USER_CODE, code, field_name), limit=1)
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
                if ticketType.code in [SUB_DEALER_CODE, END_USER_CODE]:
                    self._handle_code(
                        conflicting_ticket_sub_dealer=conflicting_ticket_sub_dealer,
                        conflicting_ticket_end_user=conflicting_ticket_end_user,
                        code=code,
                        partner=partner,
                        error_messages=error_messages,
                        ticket_type_code=ticketType.code,
                    )

    def _get_domain(self, ticket_type_code, code, field_name):
        return [
            ("helpdesk_ticket_id", "!=", False),
            ("helpdesk_ticket_type_id.code", "=", ticket_type_code),
            (f"stock_lot_id.{field_name}", "=", code),
        ]

    def _handle_code(self, **kwargs):
        conflicting_ticket_sub_dealer = kwargs.get("conflicting_ticket_sub_dealer")
        conflicting_ticket_end_user = kwargs.get("conflicting_ticket_end_user")
        code = kwargs.get("code")
        partner = kwargs.get("partner")
        error_messages = kwargs.get("error_messages")
        ticket_type_code = kwargs.get("ticket_type_code")

        if ticket_type_code != "yeu_cau_bao_hanh":
            validate_different_partner_for_sub = (
                len(conflicting_ticket_sub_dealer) > 0
                and conflicting_ticket_sub_dealer.partner_id
                and conflicting_ticket_sub_dealer.partner_id.id != partner.id
            )
            validate_different_partner_for_end = (
                len(conflicting_ticket_end_user) > 0
                and conflicting_ticket_end_user.partner_id
                and conflicting_ticket_end_user.partner_id.id != partner.id
            )
            validate_same_partner_for_sub = (
                len(conflicting_ticket_sub_dealer) > 0
                and conflicting_ticket_sub_dealer.partner_id
                and conflicting_ticket_sub_dealer.partner_id.id == partner.id
            )
            validate_same_partner_for_end = (
                len(conflicting_ticket_end_user) > 0
                and conflicting_ticket_end_user.partner_id
                and conflicting_ticket_end_user.partner_id.id == partner.id
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
            # Validate if the code is already registered on other tickets by same Partners
            elif validate_same_partner_for_sub or validate_same_partner_for_end:
                if self._is_anonymous():
                    message = f"Mã {code} đã được đăng ký cho đơn vị khác!"
                else:
                    conflicting_ticket = (
                        conflicting_ticket_sub_dealer
                        if validate_same_partner_for_sub
                        else conflicting_ticket_end_user
                    )
                    message = (
                        f"Mã {code} đã được đăng ký cho đơn vị khác, "
                        f"phiếu có mã là (#{conflicting_ticket.helpdesk_ticket_id.id})."
                    )
                error_messages.append((CODE_ALREADY_REGISTERED, message))
            # Validate if the code is already registered on other tickets with specific ticket type by current Partner
            else:
                if (
                    ticket_type_code == SUB_DEALER_CODE
                    and len(conflicting_ticket_end_user) > 0
                ):
                    if self._is_anonymous():
                        message = f"Mã {code} đã trùng với Ticket khác!"
                    else:
                        message = (
                            f"Mã {code} đã trùng với Ticket khác, "
                            f"phiếu có mã là (#{conflicting_ticket_end_user.helpdesk_ticket_id.id})."
                        )
                    error_messages.append((CODE_ALREADY_REGISTERED, message))
                elif (
                    ticket_type_code == END_USER_CODE
                    and len(conflicting_ticket_end_user) > 0
                ):
                    if self._is_anonymous():
                        message = f"Mã {code} đã trùng với Ticket khác!"
                    else:
                        message = (
                            f"Mã {code} đã trùng với Ticket khác, "
                            f"phiếu có mã là (#{conflicting_ticket_end_user.helpdesk_ticket_id.id})."
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

    def generate_ticket_details(self, request, dict_id):
        serials = request.params.get("portal_lot_serial_number")
        list_serial = serials.split(",") if serials else []
        ticket = request.env["helpdesk.ticket"].sudo().browse(dict_id.get("id"))
        ticket_type_id = request.env.ref(
            "mv_website_helpdesk.mv_helpdesk_claim_warranty_type",
            raise_if_not_found=False,
        )
        now = (
            fields.Datetime.now()
            .replace(tzinfo=pytz.UTC)
            .astimezone(pytz.timezone(request.env.user.tz or "Asia/Ho_Chi_Minh"))
        )
        if (
            int(request.params.get("ticket_type_id")) == ticket_type_id.id
            and ticket_type_id
        ):
            ticket.ticket_type_id = ticket_type_id.id
            ticket.team_id = request.env.ref(
                "mv_website_helpdesk.mv_helpdesk_claim_warranty",
                raise_if_not_found=False,
            )
        invalid_serials = ""
        for serial in list_serial:
            product_moves = (
                request.env["mv.helpdesk.ticket.product.moves"]
                .sudo()
                .search(
                    [
                        ("lot_name", "=", serial.strip()),
                        ("customer_date_activation", "!=", False),
                    ]
                )
            )
            if product_moves:
                product_moves.sudo().write(
                    {
                        "mv_warranty_ticket_id": ticket.id,
                        "mv_warranty_license_plate": request.params.get(
                            "license_plates"
                        ),
                        "mv_num_of_km": request.params.get("mileage"),
                        "mv_warranty_phone": request.params.get("mv_warranty_phone"),
                        "mv_remaining_tread_depth": request.params.get(
                            "mv_remaining_tread_depth"
                        ),
                        "mv_note_sub_branch": request.params.get("mv_note_sub_branch"),
                        "mv_reviced_date": now.date(),
                        "customer_warranty_date_activation": now.date(),
                        "mv_cv_number": request.env["ir.sequence"]
                        .sudo()
                        .next_by_code("mv.ticket.product.moves"),
                    }
                )
            if not product_moves:
                invalid_serials += serial + ", "
        if invalid_serials:
            invalid_serials = invalid_serials[0:-1]
            ticket.invalid_serials = invalid_serials

    # =============== MOVEOPLUS Override ===============
    def _handle_website_form(self, model_name, **kwargs):
        if model_name == "helpdesk.ticket" and request.params.get("team_id"):
            model_record = (
                request.env["ir.model"]
                .sudo()
                .search(
                    [("model", "=", model_name), ("website_form_access", "=", True)]
                )
            )
            if model_record:
                try:
                    data = self.extract_data(model_record, request.params)
                except Exception as error:
                    # no specific management, super will do it
                    _logger.error("Failed to extract data from the form: %s", error)
                    pass
                else:
                    if kwargs and kwargs.get("portal_lot_serial_number"):
                        # Split the string into a list
                        data_list = kwargs.get("portal_lot_serial_number").split(",")

                        # Convert the list to a set to remove duplicates, then back to a list
                        unique_data_list = list(set(data_list))

                        # Join the list back into a string
                        unique_data = ",".join(unique_data_list)
                        kwargs["portal_lot_serial_number"] = unique_data

                    tickets_data = data.get("record", {})
                    if tickets_data.get("portal_lot_serial_number"):
                        codes = (
                            request.env["helpdesk.ticket"]
                            .sudo()
                            .convert_to_list_codes(
                                tickets_data.get("portal_lot_serial_number")
                            )
                        )
                        codes_unique = list(set(codes))
                        tickets_data["portal_lot_serial_number"] = codes_unique
                    self._handle_helpdesk_ticket_form(data.get("record", {}))
                    return super(WebsiteForm, self)._handle_website_form(
                        model_name, **kwargs
                    )
        result = super(WebsiteForm, self)._handle_website_form(model_name, **kwargs)
        tmp = json.loads(result or {})
        self.generate_ticket_details(request, tmp)
        return result

    def _handle_helpdesk_ticket_form(self, record):
        # Environment Model with SUPER
        TicketTeam = request.env["helpdesk.team"].sudo()
        TicketType = request.env["helpdesk.ticket.type"].sudo()
        Partner = request.env["res.partner"].sudo()

        warranty_team = TicketTeam.browse(record.get("team_id"))
        if warranty_team and warranty_team.use_website_helpdesk_warranty_activation:
            ticket_name = record.get("name")
            ticket_type = TicketType.browse(record.get("ticket_type_id"))
            email = record.get("partner_email")
            name = record.get("partner_name")
            if email and name:
                domain = [("name", "=", name), ("email", "=", email)]
                partner = Partner.search(domain, limit=1)
                if not partner:
                    return json.dumps({"error": _("Partner not found!")})

                is_partner_agency = bool(Partner.browse(partner.id).is_agency)
                is_partner_has_parent_agency = bool(
                    Partner.browse(partner.id).parent_id.is_agency
                )
                if not is_partner_agency and not is_partner_has_parent_agency:
                    return json.dumps(
                        {
                            "error": _(
                                "Bạn không phải là Đại lý của Moveo Plus. "
                                "Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin."
                            )
                        }
                    )

                request.params["partner_id"] = partner.id

                if ticket_type and ticket_type.code in [SUB_DEALER_CODE, END_USER_CODE]:
                    type_name = ticket_type.name
                else:
                    type_name = "-"

                if not ticket_name or ticket_name and ticket_name.lower() == "new":
                    now_utc = datetime.utcnow()
                    now_user = now_utc.astimezone(pytz.timezone(partner.tz or "UTC"))
                    lang = (
                        request.env["res.lang"].sudo()._lang_get(partner.lang)
                        if partner
                        else False
                    )
                    date_format = lang.date_format
                    time_format = lang.time_format
                    formatted_date = now_user.strftime(date_format + " " + time_format)

                    partner_name = partner.name.upper() if partner else "-"
                    record["name"] = f"{partner_name}/{type_name}({formatted_date})"
