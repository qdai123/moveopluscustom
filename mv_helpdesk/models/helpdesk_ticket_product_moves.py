# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class HelpdeskTicketProductMoves(models.Model):
    _name = "mv.helpdesk.ticket.product.moves"
    _description = _("Helpdesk Ticket & Product Moves (Stock Move Line)")
    _rec_name = "lot_name"
    _order = "lot_name desc"

    # ==== BASE Fields
    name = fields.Char(
        compute='_compute_name',
        store=True,
        copy=False,
        string="Lot/Serial Number Name",
    )
    parent_id = fields.Many2one(
        comodel_name="mv.helpdesk.ticket.product.moves",
        string="Parent ID",
        index=True,
        ondelete='set null',
    )
    helpdesk_ticket_id = fields.Many2one(
        comodel_name="helpdesk.ticket",
        string="Ticket",
        help="Helpdesk Ticket",
        readonly=True,
    )
    stock_move_line_id = fields.Many2one(
        comodel_name="stock.move.line",
        string="Product Moves (Stock Move Line)",
        readonly=True,
    )

    # ==== RELATED Fields
    # Description: These fields helps to search and trace data of Stock Move Line
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
    lot_name = fields.Char(
        related="stock_move_line_id.lot_name",
        store=True,
        readonly=True,
    )
    location_dest_id = fields.Many2one(
        comodel_name="stock.location",
        related="stock_move_line_id.location_dest_id",
        store=True,
        readonly=True,
        string="To",
    )
    result_package_id = fields.Many2one(
        comodel_name="stock.quant.package",
        related="stock_move_line_id.result_package_id",
        store=True,
        readonly=True,
        string="Destination Package",
    )
    quantity = fields.Float(
        related="stock_move_line_id.quantity",
        store=True,
        readonly=True,
    )
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        related="stock_move_line_id.product_uom_id",
        store=True,
        readonly=True,
        string="Unit of Measure",
    )

    @api.depends("stock_move_line_id")
    def _compute_name(self):
        for rec in self.filtered(lambda r: r.stock_move_line_id):
            rec.name = rec.stock_move_line_id.lot_name or ""

    @api.model_create_multi
    def create(self, vals_list):
        context = dict(self.env.context or {})
        portal_create = context.get("ticket_create_from_portal", False)
        helpdesk_ticket_ctx = context.get("helpdesk_ticket_id", False)
        _logger.debug(f"Portal Create = {portal_create}")
        _logger.debug(f"Helpdesk Ticket = {helpdesk_ticket_ctx}")

        for vals in vals_list:
            if 'parent_id' in vals:
                parent_ticket_stml = self.env["mv.helpdesk.ticket.product.moves"].browse(vals['parent_id'])
                vals.update({
                    "stock_move_line_id": parent_ticket_stml.stock_move_line_id.id,
                    "helpdesk_ticket_id": vals["helpdesk_ticket_id"]
                })

        res = super(HelpdeskTicketProductMoves, self).create(vals_list)
        res.action_reload_data()
        return res

    def write(self, vals):
        context = dict(self.env.context or {})
        ctx_helpdesk_ticket_id = context.get("helpdesk_ticket_id", False)
        _logger.debug(f"Helpdesk Ticket = {ctx_helpdesk_ticket_id}")

        return super(HelpdeskTicketProductMoves, self).create(vals)

    def merge_helpdesk_ticket(self, ticket_id=False):
        """ Merge helpdesk ticket.
        :param ticket_id : the ID of the Helpdesk Ticket
        :return mv.helpdesk.ticket.product.moves record resulting after merged
        """
        return self._merge_helpdesk_ticket(ticket_id=ticket_id)

    def _merge_helpdesk_ticket(self, ticket_id=False):
        for rec in self:
            if not rec.helpdesk_ticket_id:
                rec.write({
                    "helpdesk_ticket_id": ticket_id,
                    "stock_move_line_id": rec.stock_move_line_id.id
                })

    # =======================================
    # ACTION BUTTONS
    # =======================================
    def action_reload_data(self):
        ticket_has_product_moves = self.env["helpdesk.ticket"].search(
            [("helpdesk_ticket_product_move_ids", "in", self.ids)]
        )
        if ticket_has_product_moves:
            for record in self.filtered(lambda r: r.parent_id and r.helpdesk_ticket_id in ticket_has_product_moves.ids):
                self.env.cr.execute(
                    "UPDATE mv_helpdesk_ticket_product_moves SET helpdesk_ticket_id = %s WHERE id = %s",
                    [record.helpdesk_ticket_id.id, record.parent_id.id]
                )
                self.env.cr.execute(
                    "DELETE FROM mv_helpdesk_ticket_product_moves WHERE id = %s",
                    [record.parent_id.id]
                )
                self.env.cr.commit()

    # =======================================
    # ACTION CRON
    # =======================================

    @api.model
    def _auto_generate_ticket_product_moves_data(self):
        self.env.cr.execute(
            """
                SELECT id AS product_move_id
                FROM stock_move_line
                WHERE id NOT IN
                      (SELECT DISTINCT stock_move_line_id
                       FROM mv_helpdesk_ticket_product_moves
                       WHERE stock_move_line_id IS NOT NULL)
                ORDER BY product_move_id;
            """
        )
        product_moves = self.env.cr.fetchall()
        if product_moves:
            vals_list = []
            for data in product_moves:
                vals_list.append({
                    "helpdesk_ticket_id": False,
                    "stock_move_line_id": data[0]
                })
            self.sudo().create(vals_list)

        return False
