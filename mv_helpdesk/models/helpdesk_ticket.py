# -*- coding: utf-8 -*-
import logging
from datetime import datetime

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Default Ticket Type Data for Moveoplus (Name Only)
ticket_type_sub_dealer = 'Kích Hoạt Bảo Hành Lốp Xe Continental (Sub)'
ticket_type_end_user = 'Kích Hoạt Bảo Hành Lốp Xe Continental (Người dùng cuối)'


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    helpdesk_ticket_product_move_ids = fields.One2many(
        comodel_name='mv.helpdesk.ticket.product.moves',
        inverse_name='helpdesk_ticket_id',
        string="Lot/Serial Number",
    )
    # For Ticket Type is Sub-Dealer
    is_sub_dealer = fields.Boolean(compute='_compute_ticket_type')
    sub_dealer_name = fields.Char(string="Sub-Dealer")
    # For Ticket Type is End User
    is_end_user = fields.Boolean(compute='_compute_ticket_type')
    license_plates = fields.Char(string="License plates")
    mileage = fields.Integer(default=0, string="Mileage (Km)")

    # SUPPORT Fields
    portal_lot_serial_number = fields.Text(string="Input Lot/Serial Number")
    can_import_lot_serial_number = fields.Boolean(string="Can Import?", readonly=True)

    # INHERIT Fields:
    name = fields.Char(
        compute="_compute_name",
        store=True,
        readonly=False,
        required=False,
        tracking=False
    )

    @api.depends("partner_id", "ticket_type_id")
    def _compute_name(self):
        for rec in self:
            if rec.partner_id and rec.ticket_type_id:
                rec.name = "{}/{}/{}".format(
                    rec.partner_id.name.upper() if rec.partner_id else "-",
                    rec.ticket_type_id.name,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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

    @api.model
    def create(self, vals):
        res = super(HelpdeskTicket, self).create(vals)

        if res:
            ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
            move_line_env = self.env["stock.move.line"]

            if "portal_lot_serial_number" in vals and vals.get("portal_lot_serial_number"):
                call_action_validate_lot_serial_number = self.with_context(
                    val_portal_lot_serial_number=vals.get("portal_lot_serial_number")
                ).action_scan_lot_serial_number()

                res["can_import_lot_serial_number"] = call_action_validate_lot_serial_number
                if res["can_import_lot_serial_number"]:
                    pass
                else:
                    messages_list = self._validation_portal_lot_serial_number(
                        self._format_portal_lot_serial_number(vals["portal_lot_serial_number"])
                    )
                    stock_move_line_ids = [move_line[0] for move_line in messages_list if isinstance(move_line[0], int)]
                    for stock_move_line in move_line_env.search([("id", "in", stock_move_line_ids)]):
                        if stock_move_line:
                            ticket_stock_move_line_exist = ticket_product_moves_env.search([
                                ("stock_move_line_id", "=", stock_move_line.id)
                            ])
                            if ticket_stock_move_line_exist:
                                ticket_stock_move_line_exist.write({"helpdesk_ticket_id": res["id"]})
                            else:
                                ticket_product_moves_env.create({
                                    "stock_move_line_id": stock_move_line.id,
                                    "helpdesk_ticket_id": res["id"]
                                })

                    if ("name" in vals
                            and vals.get("name")
                            and vals.get("name").lower() == "new"):
                        res._compute_name()

                    # CLEAR Lot/Serial Number Input when data Import DONE
                    res.clear_portal_lot_serial_number_input()
        return res

    def write(self, vals):
        ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
        move_line_env = self.env["stock.move.line"]

        if "portal_lot_serial_number" in vals and vals.get("portal_lot_serial_number"):
            call_action_validate_lot_serial_number = self.with_context(
                    val_portal_lot_serial_number=vals.get("portal_lot_serial_number")
            ).action_scan_lot_serial_number()

            vals["can_import_lot_serial_number"] = call_action_validate_lot_serial_number
            if vals["can_import_lot_serial_number"]:
                pass
            else:
                messages_list = self._validation_portal_lot_serial_number(
                    self._format_portal_lot_serial_number(vals["portal_lot_serial_number"])
                )
                stock_move_line_ids = [move_line[0] for move_line in messages_list if isinstance(move_line[0], int)]
                for stock_move_line in move_line_env.search([("id", "in", stock_move_line_ids)]):
                    if stock_move_line:
                        ticket_stock_move_line_exist = ticket_product_moves_env.search([
                            ("stock_move_line_id", "=", stock_move_line.id)
                        ])
                        if ticket_stock_move_line_exist:
                            ticket_stock_move_line_exist.write({"helpdesk_ticket_id": self.id})
                        else:
                            ticket_product_moves_env.create({
                                "stock_move_line_id": stock_move_line.id,
                                "helpdesk_ticket_id": self.id
                            })
                vals["portal_lot_serial_number"] = ""

        return super(HelpdeskTicket, self).write(vals)

    def clear_portal_lot_serial_number_input(self):
        self.write({"portal_lot_serial_number": ""})

    def action_import_lot_serial_number(self):
        ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
        move_line_env = self.env["stock.move.line"]

        context = self.env.context.copy()
        context["importing"] = True

        import_successfully = False
        for record in self:
            serial_numbers_fmt_list = self._format_portal_lot_serial_number(record.portal_lot_serial_number)
            if record.can_import_lot_serial_number:
                try:
                    for stock_move_line in move_line_env.search([("lot_name", "in", serial_numbers_fmt_list)]):
                        stock_move_line_ids = (
                            record.helpdesk_ticket_product_move_ids.mapped("stock_move_line_id").ids
                        ) if record.helpdesk_ticket_product_move_ids else []
                        if stock_move_line_ids and stock_move_line.id in stock_move_line_ids:
                            raise UserError(
                                _("The serial number %s has been registered in ticket.") % stock_move_line.lot_name
                            )
                        ticket_product_moves_env.create({
                            "stock_move_line_id": stock_move_line.id,
                            "helpdesk_ticket_id": record.id
                        })
                    import_successfully = True
                except Exception as e:
                    raise UserError(_("An error occurred while importing Lot/Serial Number: \n- %s") % str(e))

            if import_successfully:
                try:
                    record.portal_lot_serial_number = ""
                    record.can_import_lot_serial_number = False
                except Exception as e:
                    raise UserError(_("An error occurred while updating record attributes: %s") % str(e))

    def action_scan_lot_serial_number(self):
        context = self.env.context.copy()
        context["scanning"] = True
        self_context = self.with_context(context)
        portal_lot_serial_number = (
                self.env.context.get("val_portal_lot_serial_number", "")
                or
                self_context.portal_lot_serial_number
        )
        serial_numbers_fmt_list = self_context._format_portal_lot_serial_number(portal_lot_serial_number)
        messages_list = self_context._validation_portal_lot_serial_number(serial_numbers_fmt_list)

        for message in messages_list:
            if message[0] in ["serial_number_is_empty", "serial_number_not_found", "serial_number_already_registered"]:
                raise ValidationError(message[1])

        return True

    def _format_portal_lot_serial_number(self, text=None):
        """Return list of Lot/Serial Number input from User"""
        translation_table = str.maketrans('', '', '.,')
        text_convert = ','.join(text.splitlines())  # Convert string has multiline to text1,text2,text3
        text_list = [str(num).strip().translate(translation_table) for num in text_convert.split(',')]
        # Remove Duplicate
        result = list(set(text_list))
        return result

    def _validation_portal_lot_serial_number(self, serial_numbers=None):
        """Return Error/IDs of Stock Move Line, Message list when validate DONE"""
        messages_list = []
        ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
        move_line_env = self.env["stock.move.line"]

        if serial_numbers is None:
            serial_numbers = []

        if not serial_numbers:
            message = ("serial_number_is_empty", "Vui lòng nhập vào mã để tiến hành kiểm tra!")
            messages_list.append(message)

        if serial_numbers:
            for number in serial_numbers:
                # [ERROR] Lot/Serial Number not found in Stock
                if number not in move_line_env.search([("lot_name", "!=", "")]).mapped("lot_name"):
                    message = (
                        "serial_number_not_found",
                        "Mã %s không tồn tại trên hệ thống hoặc chưa cập nhât, "
                        "vui lòng kiểm tra lại." % number
                    )
                    messages_list.append(message)
                else:
                    # [ERROR] Lot/Serial Number has been registered to activate the Warranty
                    if ticket_product_moves_env.search([
                        ("stock_move_line_id", "!=", False),
                        ("helpdesk_ticket_id", "!=", False)
                    ]).filtered(lambda r: r.lot_name == number):
                        message = (
                            "serial_number_already_registered",
                            "Mã %s đã trùng với Ticket khác." % number
                        )
                        messages_list.append(message)
                    else:
                        # [PASS] Lot/Serial Number ready to register for Warranty activation
                        for move_line in move_line_env.search([("lot_name", "=", str(number))]):
                            message = (
                                move_line.id,
                                "%s - %s" % (
                                    move_line.lot_name,
                                    move_line.product_id.name if move_line.product_id else "<Product not found>"
                                ))
                            messages_list.append(message)

        return messages_list
