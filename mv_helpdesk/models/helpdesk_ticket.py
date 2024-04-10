# -*- coding: utf-8 -*-
import cv2
import logging
from datetime import datetime
from pyzbar.pyzbar import decode

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

# Default Ticket Type Data for Moveoplus (Name Only)
ticket_type_sub_dealer = "Kích Hoạt Bảo Hành Lốp Xe Continental (Sub)"
ticket_type_end_user = "Kích Hoạt Bảo Hành Lốp Xe Continental (Người dùng cuối)"

# Initialize the camera
cap = cv2.VideoCapture(0)  # Use the correct camera index

# Check if the camera opened successfully
if not cap.isOpened():
    print("Error: Camera could not be accessed.")
    exit()


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    def _default_team_id(self):
        team_id = self.env["helpdesk.team"].search([
            ("member_ids", "in", self.env.uid),
            ("use_website_helpdesk_warranty_activation", "=", True)
        ], limit=1).id
        if not team_id:
            team_id = self.env["helpdesk.team"].search([], limit=1).id
        return team_id

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
        tracking=False
    )
    team_id = fields.Many2one(
        comodel_name="helpdesk.team",
        string='Helpdesk Team',
        default=_default_team_id,
        index=True,
        tracking=True,
    )
    ticket_type_id = fields.Many2one(
        comodel_name="helpdesk.ticket.type",
        string="Type",
        tracking=True,
    )

    # ================== PORTAL WARRANTY ACTIVATION FORM
    portal_lot_serial_number = fields.Text(string="Input Lot/Serial Number")
    can_import_lot_serial_number = fields.Boolean(string="Can Import?", readonly=True)
    ticket_warranty_activation = fields.Boolean(
        compute="_compute_ticket_warranty_activation",
        string="Warranty Ticket",
        store=True,
    )
    # For Ticket Type is Sub-Dealer
    is_sub_dealer = fields.Boolean(compute='_compute_ticket_type')
    sub_dealer_name = fields.Char(string="Sub-Dealer")
    # For Ticket Type is End User
    is_end_user = fields.Boolean(compute='_compute_ticket_type')
    license_plates = fields.Char(string="License plates")
    mileage = fields.Integer(default=0, string="Mileage (Km)")

    @api.onchange("team_id", "ticket_warranty_activation")
    def onchange_team_id(self):
        if self.team_id and self.team_id.use_website_helpdesk_warranty_activation and self.ticket_warranty_activation:
            domain = ["|", ("name", "=", ticket_type_sub_dealer), ("name", "=", ticket_type_end_user)]
            return {"domain": {"ticket_type_id": domain}}

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

    @api.depends("team_id", "team_id.use_website_helpdesk_warranty_activation")
    def _compute_ticket_warranty_activation(self):
        for ticket in self:
            ticket.ticket_warranty_activation = False
            if ticket.team_id and ticket.team_id.use_website_helpdesk_warranty_activation:
                ticket.ticket_warranty_activation = True
                ticket.onchange_team_id()

    # ==================================
    # ORM Methods
    # ==================================

    @api.model
    def create(self, vals):
        res = super(HelpdeskTicket, self).create(vals)

        if res and vals.get("name") == "new":
            res._compute_name()

        if res and "portal_lot_serial_number" in vals and vals.get("portal_lot_serial_number"):
            scanning_pass = res.action_scan_lot_serial_number(vals.get("portal_lot_serial_number"))
            if scanning_pass:
                res._import_lot_serial_numbers(res, vals)

            # Clear Lot/Serial Number Input when data Import is DONE
            res.clear_portal_lot_serial_number_input()

        return res

    def write(self, vals):
        portal_lot_serial_number = vals.get("portal_lot_serial_number")
        if portal_lot_serial_number:
            scanning_pass = self.action_scan_lot_serial_number(portal_lot_serial_number)
            if scanning_pass:
                self._import_lot_serial_numbers(self, vals)

            self.clear_portal_lot_serial_number_input()

        return super(HelpdeskTicket, self).write(vals)

    # ==================================
    # BUSINESS Methods
    # ==================================

    def open_scanner(self):
        try:
            while True:
                # Capture frame-by-frame
                ret, frame = cap.read()

                # Check if frame is read correctly
                if not ret:
                    print("Error: Frame could not be read.")
                    break

                # Decode the frame
                decoded_objects = decode(frame)
                for obj in decoded_objects:
                    print('Type:', obj.type)
                    print('Data:', obj.data.decode('utf-8'))

                # Display the resulting frame
                cv2.imshow('Frame', frame)

                # Break the loop with 'q'
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        finally:
            # When everything done, release the capture
            cap.release()
            cv2.destroyAllWindows()

    def process_lot_serial_number(self, vals=None, action=False):
        """Actions: Create, Write, Scanning & Importing"""
        ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
        move_line_env = self.env["stock.move.line"]
        context = self.env.context.copy()
        context["importing"] = action not in ["scanning", "create", "write"]

        if vals and "portal_lot_serial_number" in vals:  # Create Data
            portal_lot_serial_number = vals.get("portal_lot_serial_number")
        elif action == "write":  # Write Data
            portal_lot_serial_number = self.portal_lot_serial_number
        else:
            portal_lot_serial_number = ""

        serial_numbers_fmt_list = self._format_portal_lot_serial_number(portal_lot_serial_number)
        messages_list = self._validation_portal_lot_serial_number(serial_numbers_fmt_list)

        for message in messages_list:
            if message[0] in ["serial_number_is_empty", "serial_number_not_found", "serial_number_already_registered"]:
                raise ValidationError(message[1])

        if action == "write":
            if self.can_import_lot_serial_number:
                try:
                    for stock_move_line in move_line_env.search([("lot_name", "in", serial_numbers_fmt_list)]):
                        stock_move_line_ids = (
                            self.helpdesk_ticket_product_move_ids.mapped("stock_move_line_id").ids
                        ) if self.helpdesk_ticket_product_move_ids else []
                        if stock_move_line_ids and stock_move_line.id in stock_move_line_ids:
                            raise UserError(
                                _("The serial number %s has been registered in a ticket.") % stock_move_line.lot_name
                            )
                        ticket_product_moves_env.create({
                            "stock_move_line_id": stock_move_line.id,
                            "helpdesk_ticket_id": self.id
                        })
                except Exception as e:
                    raise UserError(_("An error occurred while importing Lot/Serial Number: \n- %s") % str(e))
            else:
                raise UserError(_("You are not allowed to import Lot/Serial Numbers in this ticket."))
        else:
            vals = {"portal_lot_serial_number": ""}
            if "can_import_lot_serial_number" in vals:
                vals["can_import_lot_serial_number"] = False

        try:
            if action == "write":
                self.write(vals)
        except Exception as e:
            raise UserError(_("An error occurred while updating record: %s") % str(e))

    def _import_lot_serial_numbers(self, res, vals):
        ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
        move_line_env = self.env["stock.move.line"]

        messages_list = self._validation_portal_lot_serial_number(
            self._format_portal_lot_serial_number(vals["portal_lot_serial_number"])
        )
        stock_move_line_ids = [move_line[0] for move_line in messages_list if isinstance(move_line[0], int)]

        for stock_move_line in move_line_env.browse(stock_move_line_ids):
            ticket_stock_move_line_exist = ticket_product_moves_env.search([
                ("stock_move_line_id", "=", stock_move_line.id)
            ], limit=1)

            if ticket_stock_move_line_exist:
                ticket_stock_move_line_exist.write({"helpdesk_ticket_id": res.id})
            else:
                ticket_product_moves_env.create({
                    "stock_move_line_id": stock_move_line.id,
                    "helpdesk_ticket_id": res.id
                })

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

    def action_scan_lot_serial_number(self, lot_serial_number=None):
        """Scan lot serial numbers and validate them"""

        serial_numbers_fmt_list = self._format_portal_lot_serial_number(lot_serial_number)
        messages_list = self._validation_portal_lot_serial_number(serial_numbers_fmt_list)

        error_messages = [message[1] for message in messages_list if
                          message[0] in ["serial_number_is_empty",
                                         "serial_number_not_found",
                                         "serial_number_already_registered"]]

        if error_messages:
            raise ValidationError('\n'.join(error_messages))

        return True

    def _format_portal_lot_serial_number(self, text=None):
        """Return a list of Lot/Serial Numbers from user input"""
        if not text:
            return []

        # Remove special characters and split by commas
        result = ["".join(filter(str.isdigit, item)) for item in text.split(',')]

        # Remove empty strings (if any)
        result = [item for item in result if item]

        # Remove duplicates and return
        return list(set(result))

    def _validation_portal_lot_serial_number(self, serial_numbers=None):
        """Return a list of error messages or stock move line IDs for the given serial numbers"""

        messages_list = []
        ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
        move_line_env = self.env["stock.move.line"]

        if serial_numbers is None:
            serial_numbers = []

        if not serial_numbers:
            messages_list.append(("serial_number_is_empty", "Please enter serial numbers to check!"))
            return messages_list

        existing_lot_names = move_line_env.search([("lot_name", "in", serial_numbers)]).mapped("lot_name")
        existing_tickets = ticket_product_moves_env.search([("lot_name", "in", existing_lot_names)])

        for number in serial_numbers:
            if number not in existing_lot_names:
                messages_list.append(("serial_number_not_found",
                                      f"Mã {number} không tồn tại trên hệ thống hoặc chưa cập nhật. "
                                      f"\nVui lòng kiểm tra lại."))
            else:
                conflicting_ticket = existing_tickets.filtered(lambda r: r.lot_name == number and r.helpdesk_ticket_id)
                if conflicting_ticket:
                    messages_list.append(("serial_number_already_registered",
                                          f"Mã {number} đã trùng với Ticket khác. "
                                          f"\nVui lòng chọn một mã khác."))
                else:
                    move_line = move_line_env.search([("lot_name", "=", str(number))], limit=1)
                    if move_line:
                        messages_list.append(
                            (move_line.id, f"{move_line.lot_name} "
                                           f"- "
                                           f"{move_line.product_id.name if move_line.product_id else ''}"))

        return messages_list
