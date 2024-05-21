# -*- coding: utf-8 -*-
import logging
import pytz
import re
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# Default Ticket Type Data for Moveoplus (Name Only)
ticket_type_sub_dealer = "Kích Hoạt Bảo Hành Lốp Xe Continental (Sub)"
ticket_type_end_user = "Kích Hoạt Bảo Hành Lốp Xe Continental (Người dùng cuối)"

# Access Groups:
HELPDESK_USER = "helpdesk.group_helpdesk_user"
HELPDESK_MANAGER = "helpdesk.group_helpdesk_manager"


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    helpdesk_ticket_product_move_ids = fields.One2many(
        comodel_name="mv.helpdesk.ticket.product.moves",
        inverse_name="helpdesk_ticket_id",
        string="Lot/Serial Number",
    )

    # INHERIT Fields:
    name = fields.Char(
        compute="_compute_name",
        store=True,
        readonly=False,
        required=False,
        tracking=False,
    )
    ticket_type_id = fields.Many2one(
        comodel_name="helpdesk.ticket.type",
        string="Type",
        tracking=True,
    )

    # ================== PORTAL WARRANTY ACTIVATION FORM
    portal_lot_serial_number = fields.Text(string="Input Lot/Serial Number")
    can_import_lot_serial_number = fields.Boolean(string="Can Import?", readonly=True)

    # For Ticket Type is Sub-Dealer
    is_sub_dealer = fields.Boolean(compute="_compute_ticket_type")
    sub_dealer_name = fields.Char(string="Sub-Dealer")

    # For Ticket Type is End User
    is_end_user = fields.Boolean(compute="_compute_ticket_type")
    license_plates = fields.Char(string="License plates")
    mileage = fields.Integer(default=0, string="Mileage (Km)")

    # ACCESS Fields:
    is_helpdesk_manager = fields.Boolean(
        compute="_compute_is_helpdesk_manager",
        default=lambda self: self.env.user.has_group(HELPDESK_MANAGER),
    )

    @api.depends_context("uid")
    def _compute_is_helpdesk_manager(self):
        is_helpdesk_manager = self.env.user.has_group(HELPDESK_MANAGER)

        for user in self:
            user.is_helpdesk_manager = is_helpdesk_manager

    @api.depends("partner_id", "ticket_type_id")
    def _compute_name(self):
        for rec in self:
            if rec.partner_id and rec.ticket_type_id:
                user_tz = self.env.user.tz or self.env.context.get("tz")
                user_pytz = pytz.timezone(user_tz) if user_tz else pytz.utc
                now_dt = datetime.now().astimezone(user_pytz).replace(tzinfo=None)
                rec.name = "{}/{}/{}".format(
                    rec.partner_id.name.upper() if rec.partner_id else "-",
                    rec.ticket_type_id.name,
                    now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                )

    @api.depends("ticket_type_id")
    def _compute_ticket_type(self):
        for rec in self:
            rec.is_sub_dealer = False
            rec.is_end_user = False
            if rec.ticket_type_id and rec.ticket_type_id.name == ticket_type_sub_dealer:
                rec.is_sub_dealer = True
                rec.is_end_user = False
            elif rec.ticket_type_id and rec.ticket_type_id.name == ticket_type_end_user:
                rec.is_end_user = True
                rec.is_sub_dealer = False

    # ==================================
    # ORM Methods
    # ==================================

    @api.model_create_multi
    def create(self, list_value):
        tickets = super(HelpdeskTicket, self).create(list_value)

        if tickets:
            for ticket in tickets:
                for vals in list_value:
                    if vals.get("name") == "new":
                        tickets._compute_name()

                    if "portal_lot_serial_number" in vals and vals.get(
                        "portal_lot_serial_number"
                    ):
                        codes = vals["portal_lot_serial_number"]
                        scanning_pass = self.action_scan_lot_serial_number(codes)
                        if scanning_pass:
                            ticket_product_moves_env = self.env[
                                "mv.helpdesk.ticket.product.moves"
                            ]
                            move_line_env = self.env["stock.move.line"]

                            messages_list = self._validation_portal_lot_serial_number(
                                self._format_portal_lot_serial_number(
                                    vals.get("portal_lot_serial_number")
                                )
                            )
                            stock_move_line_ids = [
                                move_line[0]
                                for move_line in messages_list
                                if isinstance(move_line[0], int)
                            ]

                            for stock_move_line in move_line_env.browse(
                                stock_move_line_ids
                            ):
                                ticket_stock_move_line_exist = (
                                    ticket_product_moves_env.search(
                                        [
                                            (
                                                "stock_move_line_id",
                                                "=",
                                                stock_move_line.id,
                                            ),
                                            ("helpdesk_ticket_id", "=", False),
                                        ],
                                        limit=1,
                                    )
                                )

                                if ticket_stock_move_line_exist:
                                    ticket_stock_move_line_exist.sudo().unlink()
                                    ticket_product_moves_env.sudo().create(
                                        {
                                            "stock_move_line_id": stock_move_line.id,
                                            "helpdesk_ticket_id": ticket.id,
                                        }
                                    )
                                else:
                                    ticket_product_moves_env.sudo().create(
                                        {
                                            "stock_move_line_id": stock_move_line.id,
                                            "helpdesk_ticket_id": ticket.id,
                                        }
                                    )

                        # Clear Lot/Serial Number Input when data Import is DONE
                        ticket.clear_portal_lot_serial_number_input()

        return tickets

    def write(self, vals):
        return super(HelpdeskTicket, self).write(vals)

    def unlink(self):
        is_helpdesk_manager = self.env.user.has_group(HELPDESK_MANAGER)

        for record in self:
            not_helpdesk_manager = (
                not record.is_helpdesk_manager or not is_helpdesk_manager
            )
            not_assigned_to_user = record.user_id != self.env.user

            if not_helpdesk_manager and not_assigned_to_user:
                raise AccessError(
                    _(
                        "You are not assigned to the ticket or don't have sufficient permissions!"
                    )
                )
            elif not_helpdesk_manager and record.stage_id.name != "New":
                raise ValidationError(
                    _("You can only delete a ticket when it is in 'New' state.")
                )

        return super(HelpdeskTicket, self).unlink()

    # ==================================
    # BUSINESS Methods
    # ==================================

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
            "name": _("Wizard: Import Lot/Serial Number"),
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
