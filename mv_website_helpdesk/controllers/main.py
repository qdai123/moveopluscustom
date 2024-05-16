# -*- coding: utf-8 -*-
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
        Partner = request.env["res.partner"].sudo()

        partner_info = Partner.search(
            ["|", ("phone", "=", phone_number), ("mobile", "=", phone_number)], limit=1
        )

        if not partner_info:
            return {"partner_not_found": True}

        return {
            "partner_id": partner_info.id,
            "partner_name": partner_info.name,
            "partner_email": partner_info.email,
        }

    @http.route(
        "/mv_website_helpdesk/validate_scanned_code", type="json", auth="public"
    )
    def validate_scanned_code(self, codes):
        messages_list = []
        ticket_product_moves_env = request.env[
            "mv.helpdesk.ticket.product.moves"
        ].sudo()
        move_line_env = request.env["stock.move.line"].sudo()

        if not codes:
            messages_list.append(
                (
                    "is_empty",
                    "Vui lòng nhập vào Số lô/Mã vạch hoặc mã QR-Code để kiểm tra!",
                )
            )
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
                        f"Mã {code} không tồn tại trên hệ thống hoặc chưa cập nhật. "
                        f"\nVui lòng kiểm tra lại.",
                    )
                )
                continue

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
                        f"Mã {code} đã trùng với Ticket khác mã là (#{ticket_id})."
                        f"\nVui lòng chọn một mã khác.",
                    )
                )
            else:
                if is_qrcode:
                    move_line = move_line_env.search([("qr_code", "=", code)], limit=1)
                else:
                    move_line = move_line_env.search([("lot_name", "=", code)], limit=1)

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
        model = model_name or request.params.get("model_name")
        HelpdeskTeam = (
            (
                request.env["helpdesk.team"]
                .sudo()
                .browse(int(request.params.get("team_id")))
            )
            if request.params.get("team_id")
            else False
        )
        if (
            model == "helpdesk.ticket"
            and HelpdeskTeam
            and HelpdeskTeam.use_website_helpdesk_warranty_activation
        ):
            # Authenticated partner email exists in the System
            email = request.params.get("partner_email")
            if email:
                if request.env.user.email == email:
                    partner = request.env.user.partner_id
                else:
                    partner = (
                        request.env["res.partner"]
                        .sudo()
                        .search([("email", "=", email)], limit=1)
                    )
                if not partner:
                    # return HTTPException(description=_("Partner not found!"))
                    raise ValidationError(_("Partner not found!"))
                else:
                    request.params["partner_id"] = partner.id

            # Validated Portal Lot/Serial Number
            codes = request.params.get("portal_lot_serial_number")
            if codes:
                tickets_by_codes = (
                    request.env["helpdesk.ticket"]
                    .sudo()
                    ._validation_portal_lot_serial_number(codes)
                )
                if tickets_by_codes:
                    for ticket in tickets_by_codes:
                        if ticket[0] in ["code_not_found", "code_already_registered"]:
                            # return HTTPException(description=_(ticket[1]))
                            raise ValidationError(_(ticket[1]))

        return super(WebsiteForm, self)._handle_website_form(model_name, **kwargs)
