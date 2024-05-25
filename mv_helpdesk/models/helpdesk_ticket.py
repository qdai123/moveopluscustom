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

# Ticket Type Codes:
SUB_DEALER_CODE = "kich_hoat_bao_hanh_dai_ly"
END_USER_CODE = "kich_hoat_bao_hanh_nguoi_dung_cuoi"


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

    # INHERIT Fields:
    name = fields.Char(
        compute="_compute_name",
        store=True,
        required=False,
    )

    # ==================================================

    # Type with Sub-Dealer
    is_sub_dealer = fields.Boolean(compute="_compute_ticket_type")
    sub_dealer_name = fields.Char("Sub-Dealer")
    # Type with End-User
    is_end_user = fields.Boolean(compute="_compute_ticket_type")
    license_plates = fields.Char("License plates")
    mileage = fields.Integer("Mileage (Km)", default=0)

    # ==================================================

    # PORTAL WARRANTY ACTIVATION FORM
    portal_lot_serial_number = fields.Text(string="Input Lot/Serial Number")
    can_import_lot_serial_number = fields.Boolean(string="Can Import?", readonly=True)

    # ==================================================

    ticket_update_date = fields.Datetime(
        "Update Date", default=lambda self: fields.Datetime.now(), readonly=True
    )
    helpdesk_ticket_product_move_ids = fields.One2many(
        comodel_name="mv.helpdesk.ticket.product.moves",
        inverse_name="helpdesk_ticket_id",
        string="Lot/Serial Number",
    )

    @api.depends("partner_id", "ticket_type_id")
    def _compute_name(self):
        for rec in self:
            partner_name = rec.partner_id.name.upper() if rec.partner_id else "-"
            ticket_type_name = rec.ticket_type_id.name if rec.ticket_type_id else "-"

            now_dt = fields.Datetime.now()
            formatted_date = now_dt.strftime(DATE_FORMAT)

            rec.name = f"{partner_name}/{ticket_type_name}/{formatted_date}"

    @api.depends("ticket_type_id")
    def _compute_ticket_type(self):
        """
        Compute the ticket type based on the ticket_type_id's code.
        Sets the is_sub_dealer and is_end_user fields.
        """
        for ticket in self:
            if ticket.ticket_type_id:
                ticket.is_sub_dealer = ticket.ticket_type_id.code == SUB_DEALER_CODE
                ticket.is_end_user = ticket.ticket_type_id.code == END_USER_CODE
            else:
                ticket.is_sub_dealer = False
                ticket.is_end_user = False

    # ==================================
    # ORM Methods
    # ==================================

    @api.model_create_multi
    def create(self, list_value):
        tickets = super(HelpdeskTicket, self).create(list_value)

        for ticket in tickets:
            self._process_ticket(ticket, list_value)

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

    def _process_ticket(self, ticket, list_value):
        for vals in list_value:
            if vals.get("name") == "new":
                ticket._compute_name()

            if "portal_lot_serial_number" in vals and vals.get(
                "portal_lot_serial_number"
            ):
                self._process_lot_serial_number(
                    ticket, vals["portal_lot_serial_number"]
                )

        ticket.clear_portal_lot_serial_number_input()

    def _process_lot_serial_number(self, ticket, lot_serial_number):
        scanning_pass = self.action_scan_lot_serial_number(lot_serial_number)
        if not scanning_pass:
            return

        ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
        move_line_env = self.env["stock.move.line"]

        messages_list = self._validation_portal_lot_serial_number(
            self._format_portal_lot_serial_number(lot_serial_number)
        )

        stock_move_line_ids = [
            move_line[0] for move_line in messages_list if isinstance(move_line[0], int)
        ]

        for stock_move_line in move_line_env.browse(stock_move_line_ids):
            self._create_ticket_product_move(
                ticket, ticket_product_moves_env, stock_move_line
            )

    def _create_ticket_product_move(
        self, ticket, ticket_product_moves_env, stock_move_line
    ):
        ticket_stock_move_line_exist = ticket_product_moves_env.search(
            [
                ("stock_move_line_id", "=", stock_move_line.id),
                ("helpdesk_ticket_id", "=", False),
            ],
            limit=1,
        )

        if ticket_stock_move_line_exist:
            ticket_stock_move_line_exist.sudo().unlink()

        ticket_product_moves_env.sudo().create(
            {
                "stock_move_line_id": stock_move_line.id,
                "helpdesk_ticket_id": ticket.id,
            }
        )

    @api.model
    def convert_to_list_codes(self, codes):
        # If codes is a string, extract numbers using regex
        if isinstance(codes, str):
            lst_codes = re.findall(r"\b\d+\b", codes)
        # If codes is already a list, use it directly
        elif isinstance(codes, list):
            lst_codes = codes
        else:
            lst_codes = []

        return lst_codes

    def clear_portal_lot_serial_number_input(self):
        self.write({"portal_lot_serial_number": ""})

    def action_scan_lot_serial_number(self, codes):
        """Scan lot serial numbers and validate them"""

        if not codes:
            return False

        codes_data = self._format_portal_lot_serial_number(codes)
        messages_list = self._validation_portal_lot_serial_number(codes_data)

        error_messages = [
            message[1]
            for message in messages_list
            if message[0] in ["is_empty", "code_not_found", "code_already_registered"]
        ]

        if error_messages:
            raise ValidationError("\n".join(error_messages))

        return True

    def _format_portal_lot_serial_number(self, codes):
        if not codes:
            return []

        codes = self.convert_to_list_codes(codes)
        # Remove duplicates and return
        return list(set(codes)) if codes else []

    def _validation_portal_lot_serial_number(self, codes):
        """
        Return a list of error messages or stock move line IDs for the given Serial Numbers
        """

        messages_list = []
        ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
        move_line_env = self.env["stock.move.line"]

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
            if type(codes) is list:
                list_codes = codes
            else:
                list_codes = [c.strip() for c in codes.split(",") if c]
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
                        f"Mã {code} không tồn tại trên hệ thống hoặc chưa cập nhật.",
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
                            f"Mã {code} đã trùng với Ticket khác có mã là (#{ticket_id}).",
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
                                    move_line.id,
                                    f"{move_line.qr_code} - {move_line.product_id.name if move_line.product_id else ''}",
                                )
                            )
                        else:
                            messages_list.append(
                                (
                                    move_line.id,
                                    f"{move_line.lot_name} - {move_line.product_id.name if move_line.product_id else ''}",
                                )
                            )

        return messages_list

    def _is_qrcode(self, codes):
        if not codes:
            return False

        move_line_env = self.env["stock.move.line"]
        if type(codes) is list:
            codes_convert_to_list = codes
        else:
            codes_convert_to_list = [c.strip() for c in codes.split(",") if c]
        return move_line_env.search(
            [
                ("qr_code", "in", codes_convert_to_list),
                ("inventory_period_id", "!=", False),
            ]
        ).mapped("qr_code")

    # ==================================
    # WIZARDS Methods
    # ==================================

    def action_wizard_import_lot_serial_number(self):
        self.ensure_one()
        return {
            "name": _("Import Lot/Serial Number or QR-Code"),
            "type": "ir.actions.act_window",
            "res_model": "wizard.import.lot.serial.number",
            "view_mode": "form",
            "view_id": self.env.ref(
                "mv_helpdesk.mv_helpdesk_wizard_import_lot_serial_number_form_view"
            ).id,
            "context": {"default_helpdesk_ticket_id": self.id},
            "target": "new",
        }

    # ==================================
    # CONSTRAINS Methods
    # ==================================

    @api.constrains("portal_lot_serial_number", "helpdesk_ticket_product_move_ids")
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
            for code in codes:
                if code in lot_names or code in qr_codes:
                    raise ValidationError(
                        f"Mã {code} đã được đăng ký cho phiếu này.\nVui lòng chọn một mã khác."
                    )
