# -*- coding: utf-8 -*-
import logging
import pytz
import re
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Access Groups:
HELPDESK_USER = "helpdesk.group_helpdesk_user"
HELPDESK_MANAGER = "helpdesk.group_helpdesk_manager"

# Ticket Type Codes for Warranty Activation:
SUB_DEALER_CODE = "kich_hoat_bao_hanh_dai_ly"
END_USER_CODE = "kich_hoat_bao_hanh_nguoi_dung_cuoi"

IS_EMPTY = "is_empty"
CODE_NOT_FOUND = "code_not_found"
CODE_ALREADY_REGISTERED = "code_already_registered"


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    @api.depends_context("uid")
    def _is_helpdesk_manager(self):
        for record in self:
            record.is_helpdesk_manager = self.env.user.has_group(HELPDESK_MANAGER)

    # ACCESS / RULE Fields:
    is_helpdesk_manager = fields.Boolean(
        "Helpdesk Manager", compute="_is_helpdesk_manager"
    )

    @api.depends("partner_id", "ticket_type_id")
    def _compute_name(self):
        for rec in self:
            partner_name = rec.partner_id.name.upper() if rec.partner_id else "-"
            ticket_type_name = rec.ticket_type_id.name if rec.ticket_type_id else "-"

            now_utc = datetime.utcnow()
            now_user = now_utc.astimezone(pytz.timezone(rec.partner_id.tz or "UTC"))
            lang = self.env["res.lang"]._lang_get(rec.partner_id.lang)
            date_format = lang.date_format
            time_format = lang.time_format
            formatted_date = now_user.strftime(date_format + " " + time_format)

            rec.name = f"{partner_name}/{ticket_type_name}({formatted_date})"

    # INHERIT Fields:
    name = fields.Char(compute="_compute_name", store=True, required=False)

    # ==================================================

    portal_lot_serial_number = fields.Text("Input Lot/Serial Number")
    ticket_update_date = fields.Datetime(
        "Update Date", default=lambda self: fields.Datetime.now(), readonly=True
    )
    helpdesk_ticket_product_move_ids = fields.One2many(
        comodel_name="mv.helpdesk.ticket.product.moves",
        inverse_name="helpdesk_ticket_id",
        string="Lot/Serial Number",
    )

    # Type with Sub-Dealer
    is_sub_dealer = fields.Boolean(compute="_compute_ticket_type")
    sub_dealer_name = fields.Char("Sub-Dealer")

    # Type with End-User
    is_end_user = fields.Boolean(compute="_compute_ticket_type")
    tel_activation = fields.Char("Phone")
    license_plates = fields.Char("License plates")
    mileage = fields.Integer("Mileage (Km)", default=0)

    # ==================================
    # COMPUTE / CONSTRAINS Methods
    # ==================================

    @api.depends("ticket_type_id")
    def _compute_ticket_type(self):
        """
        Compute the ticket type based on the ticket_type_id's code.
        Sets the 'is_sub_dealer' and 'is_end_user' fields.
        """
        for ticket in self:
            if ticket.ticket_type_id:
                ticket.is_sub_dealer = ticket.ticket_type_id.code == SUB_DEALER_CODE
                ticket.is_end_user = ticket.ticket_type_id.code == END_USER_CODE
            else:
                ticket.is_sub_dealer = False
                ticket.is_end_user = False

    def _check_not_empty_portal_lot_serial_number(self):
        for record in self:
            if not record.portal_lot_serial_number:
                raise UserError(
                    "Vui lòng nhập vào Số lô/Mã vạch hoặc mã QR-Code để kiểm tra!"
                )

    def _check_codes_already_exist(self):
        for record in self:
            # Format portal lot serial numbers if needed
            codes = (
                record.portal_lot_serial_number
                if isinstance(record.portal_lot_serial_number, list)
                else self._format_portal_lot_serial_number(
                    record.portal_lot_serial_number
                )
            )

            # Get all lot names and QR codes from helpdesk_ticket_product_move_ids
            lot_names = set(record.helpdesk_ticket_product_move_ids.mapped("lot_name"))
            qr_codes = set(record.helpdesk_ticket_product_move_ids.mapped("qr_code"))

            # Check if any code already exists
            existing_codes = lot_names.union(qr_codes)
            conflicting_codes = [code for code in codes if code in existing_codes]

            if conflicting_codes:
                raise ValidationError(
                    f"The following codes are already registered for this ticket: {', '.join(conflicting_codes)}. Please select different codes."
                )

    # ==================================
    # ORM / CRUD Methods
    # ==================================

    @api.model_create_multi
    def create(self, vals_list):
        # TODO: Fix this case after
        for vals in vals_list:
            if "partner_email" in vals and "partner_name" in vals:
                partner = (
                    self.env["res.partner"]
                    .sudo()
                    .search(
                        [
                            ("name", "=", vals["partner_name"]),
                            ("email", "=", vals["partner_email"]),
                        ],
                        limit=1,
                    )
                )
                if (
                    partner
                    and not partner.is_agency
                    and not partner.parent_id.is_agency
                ):
                    raise ValidationError(
                        "Bạn không phải là Đại lý của Moveo Plus.Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin."
                    )
                vals["partner_id"] = partner.id
        tickets = super(HelpdeskTicket, self).create(vals_list)

        for ticket in tickets:
            self._process_ticket(ticket, vals_list)

        return tickets

    def write(self, vals):
        if vals:
            vals["ticket_update_date"] = fields.Datetime.now()
        return super(HelpdeskTicket, self).write(vals)

    def unlink(self):
        NEW_STATE = "New"
        NOT_ASSIGNED_ERROR = (
            "You are not assigned to the ticket or don't have sufficient permissions!"
        )
        NOT_NEW_STATE_ERROR = "You can only delete a ticket when it is in 'New' state."

        for ticket in self:
            is_not_helpdesk_manager = (
                not ticket.is_helpdesk_manager
                or not self.env.user.has_group(HELPDESK_MANAGER)
            )
            not_assigned_to_user = ticket.user_id != self.env.user

            if is_not_helpdesk_manager and not_assigned_to_user:
                raise AccessError(_(NOT_ASSIGNED_ERROR))
            elif is_not_helpdesk_manager and ticket.stage_id.name != NEW_STATE:
                raise ValidationError(_(NOT_NEW_STATE_ERROR))

            # Unlink all related ticket product moves
            ticket.helpdesk_ticket_product_move_ids.unlink()

        return super(HelpdeskTicket, self).unlink()

    # ==================================
    # BUSINESS Methods
    # ==================================

    @staticmethod
    def convert_to_list_codes(codes):
        """
        Convert the input codes into a list of codes.
        If the input is a string, extract numbers using regex.
        If the input is already a list, use it directly.
        """
        if isinstance(codes, str):
            return re.findall(r"\b\d+\b", codes)
        elif isinstance(codes, list):
            return [str(code) for code in codes if isinstance(code, (int, str))]
        return []

    def _validate_qr_code(self, codes):
        """
        Validate the input codes against existing QR codes.
        If the input is a string, split it into a list of codes.
        If the input is already a list, use it directly.
        Return the list of validated QR codes.
        """
        if isinstance(codes, str):
            valid_codes = [code.strip() for code in codes.split(",") if code]
        elif isinstance(codes, list):
            valid_codes = [str(code) for code in codes if isinstance(code, (int, str))]
        else:
            valid_codes = []

        return self.env["stock.move.line"].search(
            [("qr_code", "in", valid_codes), ("is_specify_qrcode", "=", True)]
        )

    def _validate_lot_serial_number(self, codes):
        """
        Validate the input codes against existing lot serial numbers.
        If the input is a string, split it into a list of codes.
        If the input is already a list, use it directly.
        Return the list of validated lot serial numbers.
        """
        if isinstance(codes, str):
            valid_codes = [code.strip() for code in codes.split(",") if code]
        elif isinstance(codes, list):
            valid_codes = [str(code) for code in codes if isinstance(code, (int, str))]
        else:
            valid_codes = []

        stock_lot_serial_number = self.env["stock.lot"].search(
            [("name", "in", valid_codes)]
        )
        return self.env["stock.move.line"].search(
            [("lot_id", "in", stock_lot_serial_number.ids), ("lot_name", "!=", False)]
        )

    def _process_ticket(self, ticket, vals_list):
        for vals in vals_list:
            if vals.get("name") == "new":
                ticket._compute_name()

            if "portal_lot_serial_number" in vals and vals.get(
                "portal_lot_serial_number"
            ):
                barcode = vals["portal_lot_serial_number"]
                ticket_type = ticket.ticket_type_id
                self._process_ticket_barcode(ticket, ticket_type, barcode)

        ticket.clean_data()

    def _process_ticket_barcode(self, ticket, ticket_type, barcode):
        res_ids = self._scanning(ticket, ticket_type, barcode)
        for move_line in self.env["stock.move.line"].browse(res_ids):
            self._registering_ticket_product_move(ticket, ticket_type, move_line)

    def _scanning(self, ticket, ticket_type, codes):
        """
        Validate the input codes. If the codes are not provided, raise a ValidationError.
        If the codes are provided, format them and validate them. If there are any error messages,
        raise a ValidationError with these messages. If there are no error messages, return IDs of Stock Move Line.
        """
        if not codes:
            raise ValidationError("Vui lòng nhập hoặc quét mã để quá trình tiếp tục.")

        # Convert to list of codes
        codes = self.convert_to_list_codes(codes)
        list_codes = list(set(codes)) if codes else []
        res, error_messages = self._prepare_validated_data(
            ticket, ticket_type, list_codes
        )

        if error_messages:
            raise ValidationError(
                "\n".join(
                    [
                        err_msg[1]
                        for err_msg in error_messages
                        if err_msg[0]
                        in [IS_EMPTY, CODE_NOT_FOUND, CODE_ALREADY_REGISTERED]
                    ]
                )
            )

        return res

    def _registering_ticket_product_move(self, ticket, ticket_type, stock_move_line):
        ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"].sudo()
        existing_product_none_registered = ticket_product_moves_env.search(
            [
                ("helpdesk_ticket_id", "=", False),
                ("stock_move_line_id", "=", stock_move_line.id),
            ],
            limit=1,
        )

        if existing_product_none_registered:
            existing_product_none_registered.unlink()
        else:
            if ticket_type.code == END_USER_CODE:
                ticket_product_moves_env.create(
                    {
                        "helpdesk_ticket_id": ticket.id,
                        "stock_move_line_id": stock_move_line.id,
                        "customer_phone_activation": ticket.tel_activation,
                        "customer_date_activation": fields.Date.today(),
                        "customer_license_plates_activation": ticket.license_plates,
                        "customer_mileage_activation": ticket.mileage,
                    }
                )
            elif ticket_type.code == SUB_DEALER_CODE:
                ticket_product_moves_env.create(
                    {
                        "helpdesk_ticket_id": ticket.id,
                        "stock_move_line_id": stock_move_line.id,
                    }
                )

    def _prepare_validated_data(self, ticket, ticket_type, codes):
        """
        Validate the input codes. If the codes are not provided, raise a ValueError.
        If the codes are provided, format them and validate them. If there are any error messages,
        raise a ValidationError with these messages. If there are no error messages, return IDs of Stock Move Line.
        """
        results = set()
        error_messages = []

        # [!] ===== Validate empty codes =====
        if not codes:
            error_messages.append(
                (
                    IS_EMPTY,
                    "Vui lòng nhập vào Số lô/Mã vạch hoặc mã QR-Code để kiểm tra!",
                )
            )

        validated_qr_code = self._validate_qr_code(codes)
        validated_lot_serial_number = self._validate_lot_serial_number(codes)

        # [!] ===== Validate codes are not found on system =====
        if codes and not validated_qr_code and not validated_lot_serial_number:
            error_messages.append(
                (
                    CODE_NOT_FOUND,
                    f"Mã {', '.join(codes) if len(codes) > 1 else codes[0]} không tồn tại trên hệ thống hoặc chưa cập nhật.",
                )
            )

        # [!] ===== Validate codes has been registered on other tickets =====
        qr_codes = list(set(validated_qr_code.mapped("qr_code")))
        lot_serial_numbers = list(set(validated_lot_serial_number.mapped("lot_name")))

        # QR-Codes VALIDATION
        if qr_codes:
            self._validate_codes(
                qr_codes, ticket_type, ticket.partner_id, error_messages, "qr_code"
            )

        # Lot/Serial Number VALIDATION
        if lot_serial_numbers:
            self._validate_codes(
                lot_serial_numbers,
                ticket_type,
                ticket.partner_id,
                error_messages,
                "lot_name",
            )

        # Merge the results and remove duplicates by using a set
        results.update(validated_qr_code.ids)
        results.update(validated_lot_serial_number.ids)

        # Convert the set back to a list
        results = list(results)
        error_messages = list(set(error_messages))

        return results, error_messages

    def _validate_codes(self, codes, ticket_type, partner, error_messages, field_name):
        TicketProductMoves = self.env["mv.helpdesk.ticket.product.moves"].sudo()

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
                message = (
                    f"Mã {code} đã trùng với Ticket khác, "
                    f"phiếu có mã là (#{conflicting_ticket_end_user.helpdesk_ticket_id.id})."
                )
                error_messages.append((CODE_ALREADY_REGISTERED, message))
            elif (
                ticket_type_code == END_USER_CODE
                and len(conflicting_ticket_end_user) > 0
            ):
                message = (
                    f"Mã {code} đã trùng với Ticket khác, "
                    f"phiếu có mã là (#{conflicting_ticket_end_user.helpdesk_ticket_id.id})."
                )
                error_messages.append((CODE_ALREADY_REGISTERED, message))

    def clean_data(self):
        self.write({"portal_lot_serial_number": ""})

    # ==================================
    # ACTION / BUTTON / WIZARD Methods
    # ==================================

    def action_wizard_import_lot_serial_number(self):
        # TODO: This method needs to be upgraded to support scanning with images
        self.ensure_one()
        return {
            "name": _("Import Lot/Serial Number or QR-Code"),
            "type": "ir.actions.act_window",
            "res_model": "wizard.import.lot.serial.number",
            "view_mode": "form",
            "view_id": self.env.ref(
                "mv_helpdesk.mv_helpdesk_wizard_import_lot_serial_number_form_view"
            ).id,
            "context": {
                "default_helpdesk_ticket_id": self.id,
                "default_helpdesk_ticket_type_id": self.ticket_type_id.id,
            },
            "target": "new",
        }
