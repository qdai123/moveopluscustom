# -*- coding: utf-8 -*-
import logging
from collections import defaultdict

from odoo.addons.mv_helpdesk.models.helpdesk_ticket import (
    SUB_DEALER_CODE,
    END_USER_CODE,
    HELPDESK_MANAGER,
)

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)


NEW_STATE = "mv_website_helpdesk.warranty_stage_new"
NOT_ASSIGNED_ERROR = (
    "You are not assigned to the ticket or don't have sufficient permissions!"
)
NOT_NEW_STATE_ERROR = "You can only delete a ticket when it is in 'New' state."


class HelpdeskTicketProductMoves(models.Model):
    _name = "mv.helpdesk.ticket.product.moves"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = _("Helpdesk Ticket & Product Moves & Product Stock Lot")
    _order = "helpdesk_ticket_ref desc"

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
        compute="_compute_product_activate_twice",
        store=True,
        tracking=True,
    )
    # === HELPDESK TICKET Fields ==== #
    helpdesk_ticket_id = fields.Many2one(
        "helpdesk.ticket",
        index=True,
        tracking=True,
    )
    helpdesk_ticket_ref = fields.Char(
        related="helpdesk_ticket_id.ticket_ref",
        store=True,
        tracking=True,
    )
    helpdesk_ticket_type_id = fields.Many2one(
        "helpdesk.ticket.type",
        compute="_compute_helpdesk_ticket_id",
        store=True,
        tracking=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        compute="_compute_helpdesk_ticket_id",
        store=True,
        tracking=True,
    )
    product_id = fields.Many2one(
        "product.product",
        compute="_compute_product_stock",
        store=True,
        tracking=True,
    )
    lot_name = fields.Char(
        compute="_compute_product_stock",
        store=True,
        tracking=True,
    )
    qr_code = fields.Char(
        compute="_compute_product_stock",
        store=True,
        tracking=True,
    )
    # HELPDESK TICKET Customer Activation Information (End-User Case)
    customer_phone_activation = fields.Char(
        "Số điện thoại kích hoạt",
        tracking=True,
    )
    customer_date_activation = fields.Date(
        "Ngày kích hoạt",
        tracking=True,
    )
    customer_license_plates_activation = fields.Char(
        "Biển số kích hoạt",
        tracking=True,
    )
    customer_mileage_activation = fields.Integer(
        "Số km kích hoạt",
        default=0,
        tracking=True,
    )
    customer_warranty_mileage_activation = fields.Date(tracking=True)
    # STOCK LOT Fields
    stock_lot_id = fields.Many2one(
        "stock.lot",
        "Product Stock Lot",
        context={"helpdesk_ticket_lot_name": True},
        index=True,
        tracking=True,
    )
    stock_location_id = fields.Many2one(
        "stock.location",
        related="stock_lot_id.location_id",
        store=True,
        tracking=True,
    )
    sale_order_ids = fields.Many2many("sale.order", compute="_compute_sale_order_ids")
    sale_order_count = fields.Integer(compute="_compute_sale_order_ids")
    # STOCK MOVE LINE Fields
    stock_move_line_id = fields.Many2one(
        "stock.move.line",
        context={"helpdesk_ticket_lot_name": True},
        index=True,
        tracking=True,
    )
    # STOCK MOVE LINE Related Fields
    # Description: These fields helps to search and trace data of Stock Move Line
    stock_move_id = fields.Many2one(
        "stock.move",
        related="stock_move_line_id.move_id",
        store=True,
        tracking=True,
    )

    # Fields dùng cho claim-bao-hanh
    customer_warranty_date_activation = fields.Date(
        "Ngày yêu cầu bảo hành", tracking=True
    )
    mv_warranty_ticket_id = fields.Many2one("helpdesk.ticket", tracking=True)
    mv_warranty_license_plate = fields.Char("Biển số bảo hành", tracking=True)
    mv_num_of_km = fields.Float("Số km bảo hành", tracking=True)
    mv_warranty_phone = fields.Char("Số điện thoại bảo hành", tracking=True)

    mv_cv_number = fields.Char("Số CV", tracking=True)
    mv_reviced_date = fields.Datetime("Ngày tiếp nhận", tracking=True)
    mv_result_date = fields.Datetime("Ngày trả kết quả", tracking=True)
    mv_remaining_tread_depth = fields.Float("Độ sâu gai còn lại (%)", tracking=True)
    mv_tire_installation_date = fields.Datetime("Ngày lắp lốp", tracking=True)
    mv_vehicle_pump_pressure = fields.Char("Áp suất bơm hơi", tracking=True)
    mv_number_of_tires = fields.Float("Số lốp bố", tracking=True)
    mv_mold_number = fields.Char("Số khuôn", tracking=True)

    is_warranty_product_accept = fields.Boolean(
        "Sản phẩm được đồng ý bảo hành?", tracking=True
    )
    mv_customer_warranty_date = fields.Date("Ngày bảo hành", tracking=True)
    mv_note = fields.Text("Ghi chú", tracking=True)
    mv_note_sub_branch = fields.Text("Ghi nhận từ đại lý", tracking=True)
    reason_no_warranty = fields.Text("Lý do không bảo hành", tracking=True)
    is_claim_warranty_approved = fields.Boolean("Đã duyệt", tracking=True)

    def action_claim_warranty_approved(self):
        for move in self:
            move.is_claim_warranty_approved = True
            approved_claim = move.mv_warranty_ticket_id.claim_warranty_ids.filtered(
                lambda claim: claim.is_claim_warranty_approved
            )
            all_claim = move.mv_warranty_ticket_id.claim_warranty_ids
            if len(all_claim) == len(approved_claim):
                move.mv_warranty_ticket_id.write({"can_be_create_order": True})
            else:
                move.mv_warranty_ticket_id.write({"can_be_create_order": False})
            action = {
                "name": _("Cập nhật thông tin bảo hành"),
                "type": "ir.actions.act_window",
                "res_model": "mv.helpdesk.ticket.product.moves",
                "views": [
                    [
                        self.env.ref(
                            "mv_helpdesk.mv_helpdesk_ticket_product_moves_view_form_update"
                        ).id,
                        "form",
                    ]
                ],
                "res_id": self.id,
                "view_mode": "form",
                "target": "current",
            }
            return action

    # ==================================
    # COMPUTE / INVERSE Methods
    # ==================================

    @api.onchange("customer_warranty_date_activation")
    def onchange_mv_customer_warranty_date(self):
        for move in self:
            move.mv_customer_warranty_date = move.customer_warranty_date_activation

    @api.depends("stock_lot_id")
    def _compute_sale_order_ids(self):
        sale_orders = defaultdict(lambda: self.env["sale.order"])
        for move_line in self.env["stock.move.line"].search(
            [("lot_id", "in", self.stock_lot_id.ids), ("state", "=", "done")]
        ):
            move = move_line.move_id
            if (
                move.picking_id.location_dest_id.usage == "customer"
                and move.sale_line_id.order_id
            ):
                sale_orders[move_line.lot_id.id] |= move.sale_line_id.order_id
        for record in self:
            record.sale_order_ids = sale_orders[record.stock_lot_id.id]
            record.sale_order_count = len(record.sale_order_ids)

    @api.depends("helpdesk_ticket_id")
    def _compute_helpdesk_ticket_id(self):
        for record in self:
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

    @api.depends("stock_lot_id")
    def _compute_product_stock(self):
        for record in self:
            if record.stock_lot_id:
                record.lot_name = record.stock_lot_id.name
                record.qr_code = record.stock_lot_id.ref
                record.product_id = record.stock_lot_id.product_id.id
                record.stock_location_id = record.stock_lot_id.location_id.id
            else:
                record.lot_name = False
                record.qr_code = False
                record.product_id = False
                record.stock_location_id = False

    @api.depends("stock_lot_id", "lot_name", "qr_code")
    def _compute_product_activate_twice(self):
        tickets_with_lots = self.filtered(lambda r: r.stock_lot_id)
        if not tickets_with_lots:
            return

        ticket_lots = tickets_with_lots.mapped("stock_lot_id").ids
        if not ticket_lots:
            return

        # Fetch all relevant records in a single search
        matching_tickets = self.env["mv.helpdesk.ticket.product.moves"].search(
            [("stock_lot_id", "in", ticket_lots)]
        )

        for ticket in tickets_with_lots:
            ticket_same_lot = matching_tickets.filtered(
                lambda line: line.stock_lot_id == ticket.stock_lot_id
                and line.helpdesk_ticket_type_id != ticket.helpdesk_ticket_type_id
            )
            if ticket_same_lot:
                ticket_same_lot.product_activate_twice = True
                latest_ticket = max(
                    ticket_same_lot, key=lambda r: r.helpdesk_ticket_id.create_date
                )
                ticket.product_activate_twice = (
                    latest_ticket.helpdesk_ticket_id.create_date
                    < ticket.helpdesk_ticket_id.create_date
                )
                latest_ticket.product_activate_twice = not ticket.product_activate_twice
            else:
                ticket.product_activate_twice = False

    # ==================================
    # ORM / CRUD Methods
    # ==================================

    def unlink(self):
        not_system_user = not (self.env.is_admin() or self.env.is_superuser())
        is_not_manager = self.env.user.has_group(HELPDESK_MANAGER)

        for record in self:
            not_assigned_to_user = record.helpdesk_ticket_id.user_id != self.env.user

            if not_system_user and is_not_manager and not_assigned_to_user:
                raise AccessError(_(NOT_ASSIGNED_ERROR))
            elif (
                not_system_user
                and is_not_manager
                and record.stage_id.id != self.env.ref(NEW_STATE).id
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
                    line._compute_product_stock()  # Reload Product Information
                    line._compute_helpdesk_ticket_id()  # Reload Ticket Information

                    line.customer_date_activation = line.helpdesk_ticket_id.create_date
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

    def action_update_activation_twice(self):
        """
        Update the 'product_activate_twice' field for each record in the recordset.

        This method updates the 'product_activate_twice' field based on the activation status of the product.

        :return: None
        """
        _logger.debug(
            "Starting 'action_update_activation_twice' for records: %s", self.ids
        )

        for line in self:
            try:
                line._compute_product_activate_twice()
            except Exception as e:
                _logger.error(
                    f"Failed to update activation twice for line {line.id}: {e}"
                )

        _logger.debug(
            "Completed 'action_update_activation_twice' for records: %s", self.ids
        )

    def action_open_stock(self):
        self.ensure_one()
        action = {
            "name": _("Stock Info"),
            "type": "ir.actions.act_window",
            "res_model": "stock.move",
            "res_id": self.stock_move_id.id,
            "context": {"create": False, "edit": False},
            "view_mode": "form",
            "target": "new",
        }
        return action

    def action_open_warranty_products(self):
        self.ensure_one()
        active_ids = self._context.get("active_ids", [])
        action = {
            "name": _("Cập nhật thông tin bảo hành"),
            "type": "ir.actions.act_window",
            "res_model": "mv.helpdesk.ticket.product.moves",
            "res_id": self.id,
            "view_mode": "form",
            "domain": [("id", "=", active_ids[0])],
            "target": "current",
            "context": {
                "create": False,
                "edit": True,
                "form_view_ref": "mv_helpdesk.mv_helpdesk_ticket_product_moves_view_form_update",
            },
        }
        return action

    def action_open_product(self):
        self.ensure_one()
        action = {
            "name": _("Product Info"),
            "type": "ir.actions.act_window",
            "res_model": "product.template",
            "res_id": self.product_id.product_tmpl_id.id,
            "context": {"create": False, "edit": False},
            "view_mode": "form",
            "target": "new",
        }
        return action
