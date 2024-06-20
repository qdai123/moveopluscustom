# -*- coding: utf-8 -*-
import logging
import operator
from functools import reduce

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    # === Relation from Discount Policy and Partner in Configuration ===#
    line_ids = fields.One2many(
        comodel_name="mv.discount.partner", inverse_name="partner_id"
    )
    # === Discount Policy Configuration Fields ===#
    discount_id = fields.Many2one(
        comodel_name="mv.discount",
        compute="_compute_discount_policy_ids",
        store=True,
        readonly=False,
        string="Chiết khấu sản lượng",
        help="Chính sách CHIẾT KHẤU SẢN LƯỢNG cho Đại Lý",
    )  # TODO: This field needs to be set to apply multiple policies to Partners (Many2many instead of Many2one)
    warranty_discount_policy_ids = fields.Many2many(
        comodel_name="mv.warranty.discount.policy",
        compute="_compute_discount_policy_ids",
        store=True,
        readonly=False,
        string="Chiết khấu kích hoạt",
        help="Chính sách CHIẾT KHẤU KÍCH HOẠT cho Đại Lý",
    )
    compute_discount_line_ids = fields.One2many(
        comodel_name="mv.compute.discount.line",
        inverse_name="partner_id",
        domain=[("parent_id", "!=", False)],
        string="Chi tiết: chiết khấu sản lượng",
    )
    compute_warranty_discount_line_ids = fields.One2many(
        comodel_name="mv.compute.warranty.discount.policy.line",
        inverse_name="partner_id",
        domain=[("parent_id", "!=", False)],
        string="Chi tiết: chiết khấu kích hoạt",
    )
    is_agency = fields.Boolean(
        string="Đại lý", help="Đại Lý Chính Thức của Moveo+", tracking=True
    )
    is_white_agency = fields.Boolean(
        string="Đại lý vùng trắng", help="Đại lý Vùng Trắng của Moveo+", tracking=True
    )
    is_southern_agency = fields.Boolean(
        string="Đại lý miền Nam", help="Đại lý miền Nam của Moveo+", tracking=True
    )
    bank_guarantee = fields.Boolean(
        string="Bảo lãnh ngân hàng",
        help="Đại Lý áp dụng Bảo lãnh từ Ngân hàng",
        tracking=True,
    )
    discount_bank_guarantee = fields.Float(tracking=True)
    # === Amount/Total Fields ===#
    amount = fields.Float(readonly=True)
    amount_currency = fields.Monetary(readonly=True, currency_field="currency_id")
    total_so_bonus_order = fields.Monetary(
        compute="_compute_sale_order_ids", store=True
    )
    # === Other Fields ===#
    sale_mv_ids = fields.Many2many("sale.order", readonly=True)
    currency_id = fields.Many2one("res.currency", compute="_get_company_currency")

    # =================================
    # CONSTRAINS Methods
    # =================================

    @api.constrains("is_white_agency", "is_southern_agency")
    def _check_white_and_southern_agency(self):
        for partner in self:
            if partner.is_white_agency and partner.is_southern_agency:
                raise ValidationError(
                    "Bạn chỉ có thể áp dụng cho một loại Đại lý (Con) duy nhất!"
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
    def _compute_discount_ids(self):
        for record in self:
            # Compute discount_id
            discount_line_ids = [line for line in record.line_ids if line.parent_id]
            record.discount_id = (
                discount_line_ids[0].parent_id.id if discount_line_ids else False
            )

            # Compute warranty_discount_policy_ids
            warranty_line_ids = [
                [(6, 0, line.warranty_discount_policy_ids.ids)]
                for line in record.line_ids
                if len(line.warranty_discount_policy_ids) > 0
            ]
            record.warranty_discount_policy_ids = warranty_line_ids

    @api.depends("sale_order_ids")
    def _compute_sale_order_ids(self):
        for record in self:
            if record.is_agency:
                record.sale_mv_ids = None
                total_so_bonus_money = 0
                total_discount_money = 0

                orders_discount = [
                    order
                    for order in record.sale_order_ids
                    if order.bonus_order > 0 and order.state in ["sent", "sale"]
                ]
                if orders_discount:
                    record.sale_mv_ids = [
                        (6, 0, [order.id for order in orders_discount])
                    ]
                    total_so_bonus_money += reduce(
                        operator.add,
                        (order.bonus_order for order in orders_discount),
                        0,
                    )
                record.total_so_bonus_order = total_so_bonus_money

                if record.compute_discount_line_ids:
                    total_discount_money += sum(
                        line.total_money
                        for line in record.compute_discount_line_ids.filtered(
                            lambda r: r.state == "done"
                        )
                    )

                if record.compute_warranty_discount_line_ids:
                    total_discount_money += sum(
                        line.total_amount_currency
                        for line in record.compute_warranty_discount_line_ids.filtered(
                            lambda r: r.parent_state == "done"
                        )
                    )

                record.amount_currency = (
                    total_discount_money - record.total_so_bonus_order
                )

    @api.onchange("discount_id")
    def _onchange_discount_id(self):
        if self.discount_id:
            for line in self.line_ids.filtered(lambda r: r.partner_id.id == self.id):
                line.write({"needs_update": True})

    @api.onchange("warranty_discount_policy_ids")
    def _onchange_warranty_discount_policy_id(self):
        if self.warranty_discount_policy_ids:
            for line in self.line_ids.filtered(lambda r: r.partner_id.id == self.id):
                line.write({"needs_update": True})

    @api.onchange("is_white_agency")
    def _onchange_is_white_agency(self):
        if self.is_white_agency:
            self.is_agency = True

    @api.onchange("is_southern_agency")
    def _onchange_is_southern_agency(self):
        if self.is_southern_agency:
            self.is_agency = True

    @api.onchange("bank_guarantee")
    def _onchange_bank_guarantee(self):
        self.discount_bank_guarantee = 0

    # =================================
    # BUSINESS Methods
    # =================================

    def action_update_discount_amount(self):
        for partner in self.filtered(lambda r: r.is_agency):
            partner.sale_mv_ids = [(6, 0, [])]
            partner.total_so_bonus_order = 0

            # [>] Filter orders with bonus and required state
            order_discount_confirmed = partner.sale_order_ids.filtered(
                lambda so: so.bonus_order > 0 and so.state in ["sent", "sale"]
            )
            if order_discount_confirmed:
                # [>>] Update 'sale_mv_ids' and 'total_so_bonus_order'
                partner.sale_mv_ids = [(6, 0, order_discount_confirmed.ids)]
                partner.total_so_bonus_order = sum(
                    order_discount_confirmed.mapped("bonus_order")
                )

            # [>] Calculate total discount money from different sources
            total_discount_money = sum(
                partner.compute_discount_line_ids.filtered(
                    lambda r: r.state == "done"
                ).mapped("total_money")
            ) + sum(
                partner.compute_warranty_discount_line_ids.filtered(
                    lambda r: r.parent_state == "done"
                ).mapped("total_amount_currency")
            )

            # [>] Update 'amount' and 'amount_currency'
            partner.amount = partner.amount_currency = (
                total_discount_money - partner.total_so_bonus_order
            )

            # [>.CONTEXT] Trigger update manual notification
            if self.env.context.get("trigger_manual_update", False):
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Successfully"),
                        "message": "Cập nhật tiền chiết khấu thành công",
                        "type": "success",
                        "sticky": False,
                    },
                }

        return True

    # ==================================
    # CRON SERVICE Methods
    # ==================================

    @api.model
    def _cron_recompute_partner_discount(self, limit=None):
        """
        Scheduled task to recompute the discount for partner agencies.

        Args:
            limit (int, optional): The maximum number of partners to process.
                                   If not provided, defaults to 80.

        Returns:
            bool: True if the task completed successfully, False otherwise.
        """
        records_limit = limit if limit else 80
        try:
            partners = (
                self.env["res.partner"]
                .sudo()
                .search([("is_agency", "=", True)], limit=records_limit)
            )
            for partner in partners:
                partner.with_context(
                    cron_service_run=True
                ).action_update_discount_amount()
            _logger.info(f"Recomputed discount for {len(partners)} partner agencies.")
            return True
        except Exception as e:
            _logger.error(f"Failed to recompute discount for partner agencies: {e}")
            return False
