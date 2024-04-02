# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class HelpdeskTicketProductMoves(models.Model):
    _name = "helpdesk.ticket.product.moves"
    _description = _("Helpdesk Ticket & Product Moves")

    # BASE Fields
    name = fields.Char(
        compute="_compute_name",
        store=True,
        readonly=True,
    )
    helpdesk_ticket_id = fields.Many2one(
        comodel_name="helpdesk.ticket",
        string="Helpdesk Ticket",
        readonly=True,
    )
    stock_move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
        string="Product Moves (Stock Move Line)",
        readonly=True,
    )

    # RELATED Fields
    # Description: These fields helps to search and trace data of Stock Move Line
    lot_name = fields.Char(
        related="stock_move_line_id.lot_name",
        store=True,
        readonly=True,
    )
    reference = fields.Char(
        related="stock_move_line_id.reference",
        store=True,
        readonly=True,
    )
    quantity = fields.Float(
        related="stock_move_line_id.quantity",
        store=True,
        readonly=True,
    )
    quantity_product_uom = fields.Float(
        related="stock_move_line_id.quantity_product_uom",
        store=True,
        readonly=True,
    )
    stock_move_id = fields.Many2one(
        comodel_name="stock.move",
        related="stock_move_line_id.move_id",
        store=True,
        readonly=True,
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        related="stock_move_line_id.product_id",
        store=True,
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        related="stock_move_line_id.product_uom_id",
        store=True,
        readonly=True,
    )

    @api.depends("stock_move_line_id", "lot_name")
    def _compute_name(self):
        for rec in self:
            if rec.stock_move_line_id and rec.lot_name:
                rec.name = rec.lot_name
            else:
                rec.name = "Unknown"

    @api.model_create_multi
    def create(self, vals_list):
        context = dict(self.env.context or {})
        portal_create = context.get("ticket_create_from_portal", False)
        _logger.debug(f"Portal Create = {portal_create}")

        return super(HelpdeskTicketProductMoves, self).create(vals_list)

    def write(self, vals):
        context = dict(self.env.context or {})
        portal_update = context.get("ticket_update_from_portal", False)
        _logger.debug(f"Portal Update = {portal_update}")

        return super(HelpdeskTicketProductMoves, self).create(vals)
