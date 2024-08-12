# -*- coding: utf-8 -*-
import logging

from odoo.addons.mv_helpdesk.models.helpdesk_ticket import (
    END_USER_CODE,
    HELPDESK_MANAGER,
)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


class HelpdeskTicketProductMoves(models.Model):
    _name = "mv.helpdesk.ticket.product.moves"
    _description = _("Helpdesk Ticket & Product Moves (Stock Move Line)")
    _order = "partner_id, helpdesk_ticket_id"

    @api.depends("lot_name", "qr_code")
    def _compute_name(self):
        for record in self:
            try:
                if record.lot_name and record.qr_code:
                    record.name = f"{record.lot_name},{record.qr_code}"
                elif record.lot_name and not record.qr_code:
                    record.name = record.lot_name
                elif not record.lot_name and record.qr_code:
                    record.name = record.qr_code
            except Exception as e:
                _logger.error(f"Failed to compute name: {e}")
                record.name = "N/A"

    name = fields.Char(compute="_compute_name", store=True)
    product_activate_twice = fields.Boolean(
        string="Activate Twice", compute="_compute_product_activate_twice", store=True
    )
    # HELPDESK TICKET Fields
    helpdesk_ticket_id = fields.Many2one(
        comodel_name="helpdesk.ticket", string="Ticket", index=True
    )
    helpdesk_ticket_ref = fields.Char(
        "Ticket Ref.", related="helpdesk_ticket_id.ticket_ref", store=True
    )
    helpdesk_ticket_type_id = fields.Many2one(
        comodel_name="helpdesk.ticket.type",
        compute="_compute_helpdesk_ticket_id",
        store=True,
        string="Ticket Type",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner", compute="_compute_helpdesk_ticket_id", store=True
    )
    # HELPDESK TICKET Customer Activation Information (End-User Case)
    customer_phone_activation = fields.Char("Activation Phone")
    customer_date_activation = fields.Date("Activation Date")
    customer_license_plates_activation = fields.Char("License Plates")
    customer_mileage_activation = fields.Integer("Mileage (Km)", default=0)
    customer_warranty_date_activation = fields.Date("Warranty Date")
    customer_warranty_mileage_activation = fields.Date("Warranty Mileage")
    # STOCK MOVE LINE Fields
    stock_move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
        index=True,
        string="Lot/Serial Number",
        context={"helpdesk_ticket_lot_name": True},
    )
    # STOCK MOVE LINE Related Fields
    # Description: These fields helps to search and trace data of Stock Move Line
    stock_move_id = fields.Many2one(
        comodel_name="stock.move",
        related="stock_move_line_id.move_id",
        store=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        related="stock_move_line_id.product_id",
        store=True,
    )
    lot_name = fields.Char(
        string="Lot/Serial Number", related="stock_move_line_id.lot_name", store=True
    )
    qr_code = fields.Char(
        string="QR-Code", related="stock_move_line_id.qr_code", store=True
    )
    mv_warranty_license_plate = fields.Char('Biển số xe bảo hành')
    mv_num_of_km = fields.Float('Số km đã đi')
    mv_warranty_ticket_id = fields.Many2one('helpdesk.ticket', string='Helpdesk warranty ticket')

    # ==================================
    # COMPUTE / INVERSE Methods
    # ==================================

    @api.depends("helpdesk_ticket_id")
    def _compute_helpdesk_ticket_id(self):
        for record in self:
            # Compute name if required
            record._compute_name()
            try:
                ticket = record.helpdesk_ticket_id
                record.partner_id = ticket.partner_id.id if ticket.partner_id else False
                record.helpdesk_ticket_type_id = (
                    ticket.ticket_type_id.id if ticket.ticket_type_id else False
                )
            except Exception as e:
                _logger.error(
                    f"Failed to compute helpdesk ticket id for record {record.id}: {e}"
                )
                record.partner_id = False
                record.helpdesk_ticket_type_id = False

    @api.depends("stock_move_id", "lot_name", "qr_code")
    def _compute_product_activate_twice(self):
        tickets = self.filtered(lambda r: r.helpdesk_ticket_id)
        if tickets:
            ticket_activation_same_code = self.env[
                "mv.helpdesk.ticket.product.moves"
            ].search(
                [
                    ("stock_move_id", "in", tickets.mapped("stock_move_id").ids),
                    ("lot_name", "in", tickets.mapped("lot_name")),
                    ("qr_code", "in", tickets.mapped("qr_code")),
                ]
            )
            for record in tickets:
                ticket_create_date = record.helpdesk_ticket_id.create_date
                ticket_type_id = record.helpdesk_ticket_type_id.id
                ticket_stock_move_id = record.stock_move_id.id
                same_code_ticket = ticket_activation_same_code.filtered(
                    lambda r: r.stock_move_id.id == ticket_stock_move_id
                    and r.helpdesk_ticket_type_id.id != ticket_type_id
                )
                if (
                    same_code_ticket
                    and same_code_ticket.helpdesk_ticket_id.create_date
                    > ticket_create_date
                ):
                    record.product_activate_twice = False
                    same_code_ticket.product_activate_twice = True
                elif (
                    same_code_ticket
                    and same_code_ticket.helpdesk_ticket_id.create_date
                    < ticket_create_date
                ):
                    record.product_activate_twice = True
                    same_code_ticket.product_activate_twice = False
                else:
                    record.product_activate_twice = False

    # ==================================
    # ORM / CRUD Methods
    # ==================================

    def unlink(self):
        NEW_STATE = "New"
        NOT_ASSIGNED_ERROR = (
            "You are not assigned to the ticket or don't have sufficient permissions!"
        )
        NOT_NEW_STATE_ERROR = "You can only delete a ticket when it is in 'New' state."

        for record in self:
            not_system_user = not (self.env.is_admin() or self.env.is_superuser())
            is_not_manager = self.env.user.has_group(HELPDESK_MANAGER)
            not_assigned_to_user = record.helpdesk_ticket_id.user_id != self.env.user

            if not_system_user and is_not_manager and not_assigned_to_user:
                raise AccessError(_(NOT_ASSIGNED_ERROR))
            elif (
                not_system_user and is_not_manager and record.stage_id.name != NEW_STATE
            ):
                raise ValidationError(_(NOT_NEW_STATE_ERROR))

        return super(HelpdeskTicketProductMoves, self).unlink()

    # ==================================
    # ACTION / BUTTON ACTION Methods
    # ==================================

    @api.model
    def auto_remove_duplicates(self):
        """
        Automatically remove duplicate records from the 'mv.helpdesk.ticket.product.moves' model.

        This method identifies duplicate records based on a combination of relevant fields and removes them.

        :return: None
        """
        try:
            unique_records = {}
            duplicates = self.browse()

            for record in self:
                key_full_codes = (
                    record.helpdesk_ticket_id.id,
                    record.product_id.id,
                    record.lot_name,
                    record.qr_code,
                )
                key_missing_serial = (
                    record.helpdesk_ticket_id.id,
                    record.product_id.id,
                    False,
                    record.qr_code,
                )
                key_missing_qrcode = (
                    record.helpdesk_ticket_id.id,
                    record.product_id.id,
                    record.lot_name,
                    False,
                )
                if key_full_codes in unique_records:
                    duplicates |= record
                elif key_missing_serial in unique_records:
                    duplicates |= record
                elif key_missing_qrcode in unique_records:
                    duplicates |= record
                else:
                    unique_records[key] = record

            if duplicates:
                duplicates.unlink()
                _logger.info(
                    f"Removed {len(duplicates)} duplicate records from 'mv.helpdesk.ticket.product.moves'."
                )

            return unique_records

        except Exception as e:
            _logger.error(f"Error in 'auto_remove_duplicates': {e}")
            raise ValidationError(_("Failed to remove duplicates!"))

    def action_reload(self):
        """
        Reload the data for each line in the recordset.

        This method removes duplicate records, reloads ticket information, product activation details,
        and updates customer activation details from the helpdesk ticket.

        :return: None
        """
        _logger.debug("Starting 'action_reload' for records: %s", self.ids)

        for line in self:
            try:
                if line.helpdesk_ticket_id:
                    line._compute_helpdesk_ticket_id()  # Reload Ticket Information
                    line._compute_product_activate_twice()  # Reload Product Activation

                    if line.helpdesk_ticket_id.ticket_type_id.code == END_USER_CODE:
                        line.customer_date_activation = (
                            line.helpdesk_ticket_id.create_date
                        )
                    else:
                        line.customer_date_activation = False

                    line.customer_phone_activation = (
                        line.helpdesk_ticket_id.tel_activation
                    )
                    line.customer_license_plates_activation = (
                        line.helpdesk_ticket_id.license_plates
                    )
                    line.customer_mileage_activation = line.helpdesk_ticket_id.mileage
                else:
                    line.customer_phone_activation = False
                    line.customer_date_activation = False
                    line.customer_license_plates_activation = False
                    line.customer_mileage_activation = False
            except Exception as e:
                _logger.error(f"Failed to reload data for line {line.id}: {e}")

        _logger.debug("Completed 'action_reload' for records: %s", self.ids)

    def action_open_stock(self):
        self.ensure_one()
        action = {
            "name": _("Ticket & Stock"),
            "type": "ir.actions.act_window",
            "res_model": "stock.move",
            "res_id": self.stock_move_id.id,
            "context": {"create": False, "edit": False},
            "view_mode": "form",
            "target": "new",
        }
        return action

    def action_open_product(self):
        self.ensure_one()
        action = {
            "name": _("Ticket & Product"),
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "res_id": self.product_id.id,
            "context": {"create": False, "edit": False},
            "view_mode": "form",
            "target": "new",
        }
        return action
