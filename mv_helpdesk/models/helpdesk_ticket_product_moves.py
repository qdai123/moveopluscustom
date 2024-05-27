# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.mv_helpdesk.models.helpdesk_ticket import (
    HELPDESK_MANAGER,
    END_USER_CODE,
)

_logger = logging.getLogger(__name__)


class HelpdeskTicketProductMoves(models.Model):
    _name = "mv.helpdesk.ticket.product.moves"
    _description = _("Helpdesk Ticket & Product Moves (Stock Move Line)")
    _rec_name = "lot_name"
    _order = "partner_id, helpdesk_ticket_id"

    # HELPDESK TICKET Fields
    helpdesk_ticket_id = fields.Many2one(
        comodel_name="helpdesk.ticket", string="Ticket", index=True
    )
    helpdesk_ticket_type_id = fields.Many2one(
        comodel_name="helpdesk.ticket.type",
        compute="_compute_helpdesk_ticket_id",
        inverse="_inverse_helpdesk_ticket_id",
        store=True,
        precompute=True,
        ondelete="restrict",
        string="Ticket Type",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_helpdesk_ticket_id",
        inverse="_inverse_helpdesk_ticket_id",
        store=True,
        precompute=True,
        ondelete="restrict",
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
    lot_name = fields.Char(related="stock_move_line_id.lot_name", store=True)
    qr_code = fields.Char(related="stock_move_line_id.qr_code", store=True)

    # ==================================
    # ORM Methods
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
    # COMPUTE / INVERSE Methods
    # ==================================

    @api.depends(
        "helpdesk_ticket_id",
        "helpdesk_ticket_id.partner_id",
        "helpdesk_ticket_id.ticket_type_id",
    )
    def _compute_helpdesk_ticket_id(self):
        """
        Compute the partner_id and helpdesk_ticket_type_id fields based on the helpdesk_ticket_id field.
        Sets the partner_id and helpdesk_ticket_type_id fields to the corresponding fields of the helpdesk_ticket_id if it is set, otherwise sets them to False.
        """
        for record in self:
            record.partner_id = (
                record.helpdesk_ticket_id.partner_id.id
                if record.helpdesk_ticket_id
                else False
            )
            record.helpdesk_ticket_type_id = (
                record.helpdesk_ticket_id.ticket_type_id.id
                if record.helpdesk_ticket_id
                else False
            )

    @api.onchange("helpdesk_ticket_id")
    def _inverse_helpdesk_ticket_id(self):
        """
        Inverse method for helpdesk_ticket_id field.
        Sets the partner_id and helpdesk_ticket_type_id fields to False if helpdesk_ticket_id is not set.
        """
        for record in self:
            no_ticket = not record.helpdesk_ticket_id
            record.partner_id = no_ticket
            record.helpdesk_ticket_type_id = no_ticket

    # ==================================
    # ACTION / BUTTON ACTION Methods
    # ==================================

    def action_open_stock(self):
        self.ensure_one()
        action = {
            "name": _("Stock"),
            "type": "ir.actions.act_window",
            "res_model": "stock.move",
            "context": {"create": False, "edit": False},
            "view_mode": "form",
            "target": "new",
            "res_id": self.stock_move_id.id,
        }
        return action

    def action_open_product(self):
        self.ensure_one()
        action = {
            "name": _("Product"),
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "context": {"create": False, "edit": False},
            "view_mode": "form",
            "target": "new",
            "res_id": self.product_id.id,
        }
        return action
