# -*- coding: utf-8 -*-
from functools import reduce
import operator

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    line_ids = fields.One2many("mv.discount.partner", "partner_id")
    compute_discount_line_ids = fields.One2many(
        "mv.compute.discount.line", "partner_id", domain=[("parent_id", "!=", False)]
    )
    # =================================
    is_agency = fields.Boolean("Đại lý", copy=False)
    is_white_agency = fields.Boolean("Đại lý vùng trắng", copy=False)

    bank_guarantee = fields.Boolean("Bảo lãnh ngân hàng", copy=False)
    discount_bank_guarantee = fields.Float(copy=False)

    # COMPUTE Fields:
    sale_mv_ids = fields.One2many("sale.order", "partner_id", "Discount Sales Order")
    discount_id = fields.Many2one(
        "mv.discount",
        string="Chiết khấu",
        compute="_compute_discount_ids",
        store=True,
        readonly=False,
    )
    warranty_discount_policy_id = fields.Many2one(
        "mv.warranty.discount.policy",
        string="Chiết khấu kích hoạt",
        compute="_compute_discount_ids",
        store=True,
        readonly=False,
    )

    # TOTAL Fields:
    currency_id = fields.Many2one("res.currency", compute="_get_company_currency")
    amount = fields.Integer("Tiền chiết khấu", copy=False)
    amount_currency = fields.Monetary(
        string="Tiền chiết khấu hiện có",
        compute="_compute_sale_order_ids",
        store=True,
    )
    total_so_bonus_order = fields.Monetary(
        "Tổng tiền chiết khấu", compute="_compute_sale_order_ids", store=True
    )

    # =================================
    # COMPUTE / ONCHANGE Methods
    # =================================

    def _get_company_currency(self):
        for partner in self:
            company = partner.company_id or self.env.company
            partner.currency_id = company.sudo().currency_id

    @api.depends("line_ids")
    def _compute_discount_ids(self):
        for record in self:
            # Compute discount_id
            discount_line_ids = [line for line in record.line_ids if line.parent_id]
            record.discount_id = (
                discount_line_ids[0].parent_id.id if discount_line_ids else False
            )

            # Compute warranty_discount_policy_id
            warranty_line_ids = [
                line for line in record.line_ids if line.warranty_discount_policy_id
            ]
            record.warranty_discount_policy_id = (
                warranty_line_ids[0].warranty_discount_policy_id.id
                if warranty_line_ids
                else False
            )

    @api.depends("sale_order_ids")
    def _compute_sale_order_ids(self):
        for record in self.filtered(
            lambda partner: partner.is_agency
            and partner.discount_id
            and partner.sale_order_ids
        ):
            record.sale_mv_ids = None
            orders_discount = [
                order
                for order in record.sale_order_ids
                if order.bonus_order > 0 and order.state != "cancel"
            ]
            if orders_discount:
                record.sale_mv_ids = [(6, 0, [order.id for order in orders_discount])]

            record.total_so_bonus_order = reduce(
                operator.add, (order.bonus_order for order in orders_discount), 0
            )
            record.amount_currency = record.total_so_bonus_order

    @api.onchange("discount_id")
    def _onchange_discount_id(self):
        if self.discount_id:
            for line in self.line_ids.filtered(lambda r: r.partner_id.id == self.id):
                line.write({"needs_update": True})

    @api.onchange("warranty_discount_policy_id")
    def _onchange_warranty_discount_policy_id(self):
        if self.warranty_discount_policy_id:
            for line in self.line_ids.filtered(lambda r: r.partner_id.id == self.id):
                line.write({"needs_update": True})

    @api.onchange("is_white_agency")
    def _onchange_is_white_agency(self):
        if self.is_white_agency:
            self.is_agency = True

    @api.onchange("bank_guarantee")
    def _onchange_bank_guarantee(self):
        self.discount_bank_guarantee = 0
