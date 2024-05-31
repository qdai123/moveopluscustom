# -*- coding: utf-8 -*-
from functools import reduce
import operator

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    line_ids = fields.One2many("mv.discount.partner", "partner_id")
    discount_id = fields.Many2one(
        "mv.discount",
        string="Chiết khấu",
        compute="_compute_discount_id",
        store=True,
        readonly=False,
    )
    warranty_discount_policy_id = fields.Many2one(
        "mv.warranty.discount.policy",
        string="Chiết khấu kích hoạt",
        compute="_compute_warranty_discount_policy_id",
        store=True,
        readonly=False,
    )
    compute_discount_line_ids = fields.One2many(
        "mv.compute.discount.line", "partner_id", domain=[("parent_id", "!=", False)]
    )
    is_agency = fields.Boolean("Đại lý", copy=False)
    is_white_agency = fields.Boolean("Đại lý vùng trắng", copy=False)
    bank_guarantee = fields.Boolean("Bảo lãnh ngân hàng", copy=False)
    discount_bank_guarantee = fields.Float("Bảo lãnh ngân hàng", copy=False)
    sale_mv_ids = fields.Many2many("sale.order", compute="_compute_sale_mv_ids")
    currency_id = fields.Many2one(
        "res.currency",
        compute="_get_company_currency",
        readonly=True,
    )
    # TOTAL Fields:
    amount = fields.Integer("Tiền chiết khấu", copy=False)
    amount_currency = fields.Monetary(
        string="Tiền chiết khấu hiện có",
        compute="_compute_total_amount_discount",
        store=True,
        currency_field="currency_id",
    )
    total_so_bonus_order = fields.Monetary(
        "Tổng tiền chiết khấu",
        compute="_compute_total_amount_discount",
        store=True,
        currency_field="currency_id",
    )

    # =================================
    # COMPUTE / ONCHANGE Methods
    # =================================

    def _get_company_currency(self):
        for partner in self:
            if partner.company_id:
                partner.currency_id = partner.sudo().company_id.currency_id
            else:
                partner.currency_id = self.env.company.currency_id

    @api.depends("line_ids")
    def _compute_discount_id(self):
        for record in self:
            record.discount_id = False
            # Use list comprehension instead of filtered method
            line_ids = [line for line in record.line_ids if line.parent_id]
            # Use bool function instead of len function
            if line_ids:
                record.discount_id = line_ids[0].parent_id.id

    @api.depends("line_ids")
    def _compute_warranty_discount_policy_id(self):
        for record in self:
            record.warranty_discount_policy_id = False
            # Use list comprehension instead of filtered method
            line_ids = [
                line for line in record.line_ids if line.warranty_discount_policy_id
            ]
            # Use bool function instead of len function
            if line_ids:
                record.warranty_discount_policy_id = line_ids[
                    0
                ].warranty_discount_policy_id.id

    @api.depends("sale_order_ids")
    def _compute_sale_mv_ids(self):
        for record in self:
            # Use list comprehension instead of filtered method
            orders_discount = (
                [
                    order
                    for order in record.sale_order_ids
                    if order.bonus_order > 0 and order.state != "cancel"
                ]
                if record.sale_order_ids
                else []
            )
            if orders_discount:
                # Use bool function instead of len function
                record.sale_mv_ids = [(6, 0, [order.id for order in orders_discount])]
            else:
                record.sale_mv_ids = None

    @api.depends("sale_order_ids")
    def _compute_total_amount_discount(self):
        for record in self.filtered(
            lambda partner: partner.is_agency
            and partner.discount_id
            and len(partner.sale_order_ids) > 0
        ):
            if record.sale_order_ids or len(record.sale_order_ids) > 0:
                # Use list comprehension instead of filtered method
                orders_discount = [
                    order
                    for order in record.sale_order_ids
                    if order.bonus_order > 0 and order.state != "cancel"
                ]

                # Use reduce function instead of sum function
                record.total_so_bonus_order = reduce(
                    operator.add, (order.bonus_order for order in orders_discount), 0
                )
                record.amount_currency = reduce(
                    operator.add, (order.bonus_order for order in orders_discount), 0
                )

    @api.onchange("is_white_agency")
    def _onchange_is_white_agency(self):
        if self.is_white_agency and not self.is_agency:
            self.is_agency = True

    @api.onchange("bank_guarantee")
    def _onchange_bank_guarantee(self):
        self.discount_bank_guarantee = 0
