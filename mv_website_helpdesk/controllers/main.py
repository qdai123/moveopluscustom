# -*- coding: utf-8 -*-
import json
import logging
import requests
import pytz
import re

try:
    import phonenumbers
except ImportError:
    phonenumbers = None

from datetime import datetime
from markupsafe import Markup

from odoo import http, _, fields
from odoo.http import request, Response
from odoo.addons.phone_validation.tools import phone_validation
from odoo.addons.website.controllers import form
from odoo.exceptions import ValidationError
from odoo.osv import expression
from datetime import datetime


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

HELPDESK_CLAIM_WARRANTY_ACTIVATION_FORM = (
    "mv_website_helpdesk.mv_claim_warranty_template"
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

    @http.route("/claim-bao-hanh", type="http", auth="public", website=True)
    def website_helpdesk_claim_warranty(self, **kwargs):
        _logger.info(
            f"Method [website_helpdesk_claim_warranty] Params: {kwargs}"
        )
        WarrantyActivationTeam = (
            request.env["helpdesk.team"]
            .sudo()
            .search([("use_website_helpdesk_warranty_activation", "=", True)], limit=1)
        )
        type_sub_dealer = (
            request.env["helpdesk.ticket.type"]
            .sudo()
            .search(
                [
                    ("user_for_warranty_activation", "=", True),
                    ("code", "=", SUB_DEALER_CODE),
                ],
                limit=1,
            )
        )
        type_end_user = (
            request.env["helpdesk.ticket.type"]
            .sudo()
            .search(
                [
                    ("user_for_warranty_activation", "=", True),
                    ("code", "=", END_USER_CODE),
                ],
                limit=1,
            )
        )
        return http.request.render(
            HELPDESK_CLAIM_WARRANTY_ACTIVATION_FORM,
            {
                "anonymous": self._is_anonymous(),
                "default_helpdesk_team": WarrantyActivationTeam,
                "ticket_type_objects": request.env.ref(
                    'mv_website_helpdesk.mv_helpdesk_claim_warranty_type', raise_if_not_found=False),
                "type_is_sub_dealer_id": type_sub_dealer.id or False,
                "type_is_end_user_id": type_end_user.id or False,
            },
        )

    @http.route("/kich-hoat-bao-hanh", type="http", auth="public", website=True)
    def website_helpdesk_warranty_activation_teams(self, **kwargs):
        """
        Render the warranty activation form for sub-dealers and end-users.

        This method searches for the helpdesk team and ticket types used for warranty activation
        and renders the corresponding form template.

        Returns:
            werkzeug.wrappers.Response: The rendered HTML response.
        """
        _logger.info(
            f"Method [website_helpdesk_warranty_activation_teams] Params: {kwargs}"
        )

        # Search for the helpdesk team that uses the website helpdesk warranty activation
        WarrantyActivationTeam = (
            request.env["helpdesk.team"]
            .sudo()
            .search([("use_website_helpdesk_warranty_activation", "=", True)], limit=1)
        )

        # Define the domain for searching ticket types used for warranty activation
        domain_ticket_type_obj = [
            ("user_for_warranty_activation", "=", True),
            ("code", "in", [SUB_DEALER_CODE, END_USER_CODE]),
        ]

        # Search for the ticket type for sub-dealers
        type_sub_dealer = (
            request.env["helpdesk.ticket.type"]
            .sudo()
            .search(
                [
                    ("user_for_warranty_activation", "=", True),
                    ("code", "=", SUB_DEALER_CODE),
                ],
                limit=1,
            )
        )

        # Search for the ticket type for end-users
        type_end_user = (
            request.env["helpdesk.ticket.type"]
            .sudo()
            .search(
                [
                    ("user_for_warranty_activation", "=", True),
                    ("code", "=", END_USER_CODE),
                ],
                limit=1,
            )
        )

        # Render the warranty activation form template with the necessary context
        return http.request.render(
            HELPDESK_WARRANTY_ACTIVATION_FORM,
            {
                "anonymous": self._is_anonymous(),
                "default_helpdesk_team": WarrantyActivationTeam,
                "ticket_type_objects": request.env["helpdesk.ticket.type"]
                .sudo()
                .search(domain_ticket_type_obj, order="id"),
                "type_is_sub_dealer_id": type_sub_dealer.id or False,
                "type_is_end_user_id": type_end_user.id or False,
                "warranty_ticket_type": request.env.ref(
                    'mv_website_helpdesk.mv_helpdesk_claim_warranty_type', raise_if_not_found=False),
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
        partner_name,
        partner_email,
        tel_activation,
        by_pass_check=False,
    ):
        session_info = request.env["ir.http"].session_info()
        _logger.debug(f"Session Info: {session_info}")

        Ticket = request.env["helpdesk.ticket"].sudo()
        Partner = request.env["res.partner"].sudo()
        error_messages = []

        if ticket_type:
            ticket_type = (
                request.env["helpdesk.ticket.type"].sudo().browse(int(ticket_type))
            )
            _logger.debug(f"Ticket Type: {ticket_type}")
        else:
            ticket_type = request.env.ref('mv_helpdesk.type_guarantee_activation_for_sub_dealer', raise_if_not_found=False)

        partner = False
        if partner_email and self.is_valid_email(partner_email):
            partner = Partner.search(
                [
                    ("name", "=", partner_name),
                    ("email", "=", partner_email),
                ],
                limit=1,
            )
            is_partner_agency = bool(Partner.browse(partner.id).is_agency)
            is_partner_has_parent_agency = bool(
                Partner.browse(partner.id).parent_id.is_agency
            )
            if (
                not by_pass_check
                and not is_partner_agency
                and not is_partner_has_parent_agency
            ):
                error_messages.append(
                    (
                        IS_NOT_AGENCY,
                        "Bạn không phải là Đại lý của Moveo Plus.Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin.",
                    )
                )
                return error_messages

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
        if not by_pass_check and qrcodes:
            self._validate_codes(
                qrcodes, ticket_type, partner, error_messages, "qr_code"
            )

        # Lot/Serial Number VALIDATION
        if not by_pass_check and serial_numbers:
            self._validate_codes(
                serial_numbers, ticket_type, partner, error_messages, "lot_name"
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
        if ticket_type_code != 'yeu_cau_bao_hanh':
            validate_different_partner_for_sub = (
                len(conflicting_ticket_sub_dealer) > 0
                and conflicting_ticket_sub_dealer.partner_id.id != partner.id
            )
            validate_different_partner_for_end = (
                len(conflicting_ticket_end_user) > 0
                and conflicting_ticket_end_user.partner_id.id != partner.id
            )
            validate_same_partner_for_sub = (
                len(conflicting_ticket_sub_dealer) > 0
                and conflicting_ticket_sub_dealer.partner_id.id == partner.id
            )
            validate_same_partner_for_end = (
                len(conflicting_ticket_end_user) > 0
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
        now = fields.Datetime.now().replace(tzinfo=pytz.UTC).astimezone(
            pytz.timezone(request.env.user.tz or 'Asia/Ho_Chi_Minh'))
        serials = request.params.get('portal_lot_serial_number')
        list_serial = serials.split(",")

        ticket = request.env['helpdesk.ticket'].sudo().browse(dict_id.get('id'))
        ticket_type_id = request.env.ref('mv_website_helpdesk.mv_helpdesk_claim_warranty_type',
                                         raise_if_not_found=False)
        if int(request.params.get('ticket_type_id')) == ticket_type_id.id and \
                ticket_type_id:
            ticket.ticket_type_id = ticket_type_id.id
            ticket.team_id = request.env.ref('mv_website_helpdesk.mv_helpdesk_claim_warranty', 
                                              raise_if_not_found=False)
        invalid_serials = ''
        for serial in list_serial:
            product_moves = request.env['mv.helpdesk.ticket.product.moves'].sudo().search([
                ('lot_name', '=', serial.strip()),
                ('customer_date_activation', '!=', False)
            ])
            if product_moves:
                product_moves.sudo().write({
                    'mv_warranty_ticket_id': ticket.id,
                    'mv_warranty_license_plate': request.params.get('license_plates'),
                    'mv_num_of_km': request.params.get('mileage'),
                    'customer_warranty_date_activation': now.date(),
                })
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
                                "Bạn không phải là Đại lý của Moveo Plus.Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin."
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
