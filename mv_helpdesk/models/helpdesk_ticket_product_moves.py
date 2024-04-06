# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class HelpdeskTicketProductMoves(models.Model):
    _name = "mv.helpdesk.ticket.product.moves"
    _description = _("Helpdesk Ticket & Product Moves (Stock Move Line)")
    _rec_name = "lot_name"
    _order = "lot_name desc, helpdesk_ticket_id"

    # ==== BASE Fields
    stock_move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
        string="Lot/Serial Number",
        readonly=True,
        index=True,
        context={"helpdesk_ticket_lot_name": True},
    )
    helpdesk_ticket_id = fields.Many2one(
        comodel_name="helpdesk.ticket",
        string="Ticket",
        help="Helpdesk Ticket",
        readonly=True,
        index=True,
    )

    # ==== RELATED Fields
    # Description: These fields helps to search and trace data of Stock Move Line
    lot_name = fields.Char(
        related="stock_move_line_id.lot_name",
        store=True,
        readonly=True,
        index=True,
    )
    stock_move_id = fields.Many2one(
        comodel_name="stock.move",
        related="stock_move_line_id.move_id",
        store=True,
        readonly=True,
        string="Stock Move"
    )
    product_id = fields.Many2one(
        comodel_name="product.product",
        related="stock_move_line_id.product_id",
        store=True,
        readonly=True,
        string="Product"
    )

    @api.model_create_multi
    def create(self, vals_list):
        return super(HelpdeskTicketProductMoves, self).create(vals_list)

    def write(self, vals):
        return super(HelpdeskTicketProductMoves, self).create(vals)

    def action_open_stock(self):
        self.ensure_one()
        action = {
            'name': _("Stock"),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.move',
            'context': {'create': False, 'edit': False},
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.stock_move_id.id,
        }
        return action

    def action_open_product(self):
        self.ensure_one()
        action = {
            'name': _("Product"),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'context': {'create': False, 'edit': False},
            'view_mode': 'form',
            'target': 'new',
            'res_id': self.product_id.id,
        }
        return action

    def action_reload_data(self):
        ticket_has_product_moves = self.env["helpdesk.ticket"].search(
            [("helpdesk_ticket_product_move_ids", "in", self.ids)]
        )
        if ticket_has_product_moves:
            for record in self.filtered(lambda r: r.helpdesk_ticket_id in ticket_has_product_moves.ids):
                self.env.cr.execute(
                    "UPDATE mv_helpdesk_ticket_product_moves SET helpdesk_ticket_id = %s WHERE stock_move_line_id = %s",
                    [record.helpdesk_ticket_id.id, record.stock_move_line_id.id]
                )
                self.env.cr.commit()
