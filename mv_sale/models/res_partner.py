# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    # ===TRƯỜNG CƠ SỞ DỮ LIỆU
    # line_ids: Nội dung chi tiết chiết khấu được áp dụng cho Đại Lý
    # amount/amount_currency: Ví tiền được chiết khấu cho Đại lý sử dụng
    # sale_mv_ids: Danh sách các đơn hàng mà Đại Lý đã được áp dụng chiết khấu
    # total_so_bonus_order: Tổng số tiền chiết khấu đã được áp dụng cho các đơn hàng của Đại Lý
    # ===#
    line_ids = fields.One2many("mv.discount.partner", "partner_id", copy=False)
    currency_id = fields.Many2one(
        "res.currency", compute="_get_company_currency", readonly=True
    )
    amount = fields.Float(readonly=True)
    amount_currency = fields.Monetary(currency_field="currency_id", readonly=True)
    sale_mv_ids = fields.Many2many("sale.order", readonly=True)
    total_so_bonus_order = fields.Monetary(compute="_compute_sale_order", store=True)

    # === THÔNG TIN ĐẠI LÝ
    # Đại lý: Là nhà phân phối trực thuộc của công ty MOVEOPLUS
    # Đại lý Vùng Trắng (White Agency): Đại lý phân phối sản phẩm tại các vùng trắng
    # Đại lý Miền Nam (Southern Agency): Đại lý phân phối sản phẩm tại miền Nam
    # Bảo lãnh ngân hàng, Chiết khấu bảo lãnh ngân hàng (%)
    # ===#
    is_agency = fields.Boolean("Đại lý", tracking=True)
    is_white_agency = fields.Boolean("Đại lý vùng trắng", tracking=True)
    is_southern_agency = fields.Boolean("Đại lý miền Nam", tracking=True)
    bank_guarantee = fields.Boolean("Bảo lãnh ngân hàng", tracking=True)
    discount_bank_guarantee = fields.Float(
        "Chiết khấu bảo lãnh ngân hàng (%)", digits=(16, 2), tracking=True
    )

    # === MO+ POLICY: CHÍNH SÁCH CHIẾT KHẤU SẢN LƯỢNG ===#
    discount_id = fields.Many2one(
        "mv.discount",
        "Chiết khấu sản lượng",
        help="Chính sách 'CHIẾT KHẤU SẢN LƯỢNG' cho Đại Lý",
    )  # TODO: This field needs to be set to apply multiple policies to Partners (Many2many instead of Many2one)
    compute_discount_line_ids = fields.One2many(
        "mv.compute.discount.line",
        "partner_id",
        domain=[("parent_id", "!=", False)],
        string="Chi tiết: CHIẾT KHẤU SẢN LƯỢNG",
    )

    # === MO+ POLICY: CHÍNH SÁCH CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH ===#
    warranty_discount_policy_ids = fields.Many2many(
        "mv.warranty.discount.policy",
        string="Chiết khấu kích hoạt",
        help="Chính sách 'CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH' cho Đại Lý",
    )
    compute_warranty_discount_line_ids = fields.One2many(
        "mv.compute.warranty.discount.policy.line",
        "partner_id",
        domain=[("parent_id", "!=", False)],
        string="Chi tiết: CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH",
    )

    # =================================
    # CONSTRAINS Methods
    # =================================

    @api.constrains("is_white_agency", "is_southern_agency")
    def _check_partner_agency_child_overlap(self):
        if any(p.is_white_agency and p.is_southern_agency for p in self):
            raise UserError(
                "Đại lý không thể cùng lúc là 'Đại lý Vùng Trắng' và 'Đại lý miền Nam'"
            )

    # =================================
    # COMPUTE / ONCHANGE Methods
    # =================================

    def _get_company_currency(self):
        for partner in self:
            partner.currency_id = (
                partner.company_id.currency_id
                if partner.company_id
                else self.env.company.currency_id
            )

    @api.depends("sale_order_ids")
    def _compute_sale_order(self):
        for record in self:
            record.sale_mv_ids = None
            record.total_so_bonus_order = 0
            record.amount = record.amount_currency = 0

            orders_discount_applied = record.sale_order_ids.filtered(
                lambda order: order.state == "sale"
                and (
                    order.discount_agency_set
                    or order.order_line._filter_discount_agency_lines(order)
                )
            )
            if orders_discount_applied:
                orders_discount_applied._compute_partner_bonus()
                record.sale_mv_ids = [(6, 0, orders_discount_applied.ids)]
                record.total_so_bonus_order = sum(
                    orders_discount_applied.mapped("bonus_order")
                )

            total_amount_discount_approved = sum(
                line.total_money
                for line in record.compute_discount_line_ids.filtered(
                    lambda r: r.state == "done"
                )
            ) + sum(
                line.total_amount_currency
                for line in record.compute_warranty_discount_line_ids.filtered(
                    lambda r: r.parent_state == "done"
                )
            )

            wallet = total_amount_discount_approved - record.total_so_bonus_order
            record.amount = record.amount_currency = wallet if wallet > 0 else 0.0

    @api.onchange("is_agency")
    def _onchange_is_white_agency(self):
        self.is_white_agency = False
        self.is_southern_agency = False

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
    # ORM / CRUD Methods
    # =================================

    def write(self, vals):
        if vals.get("discount_id"):
            discount_id = self.env["mv.discount"].browse(vals["discount_id"])
            if discount_id.exists():
                vals["line_ids"] = [
                    (
                        0,
                        0,
                        {
                            "partner_id": self.id,
                            "parent_id": vals["discount_id"],
                            "warranty_discount_policy_ids": [
                                (6, 0, self.warranty_discount_policy_ids.ids)
                            ],
                            "needs_update": True,
                        },
                    )
                ]

        res = super().write(vals)

        if res and self.warranty_discount_policy_ids:
            lines_to_update = self.line_ids.filtered(
                lambda r: r.partner_id == self and not r.warranty_discount_policy_ids
            )
            if lines_to_update:
                lines_to_update.warranty_discount_policy_ids = [
                    (6, 0, self.warranty_discount_policy_ids.ids)
                ]

        return res

    # =================================
    # BUSINESS Methods
    # =================================

    def action_update_discount_amount(self):
        for partner in self.filtered("is_agency"):
            partner.sale_mv_ids = [(6, 0, [])]
            partner.total_so_bonus_order = 0

            # [>] Filter orders with discount applied and in 'sale' state
            orders_discount_applied = partner.sale_order_ids.filtered(
                lambda order: order.state == "sale"
                and (
                    order.discount_agency_set
                    or order.order_line._filter_discount_agency_lines(order)
                )
            )
            if orders_discount_applied:
                # [>>] Recompute partner bonus order for each order
                orders_discount_applied._compute_partner_bonus()
                # [>>] Replace on 'sale_mv_ids' and 'total_so_bonus_order' fields
                partner.sale_mv_ids = [(6, 0, orders_discount_applied.ids)]
                partner.total_so_bonus_order = sum(
                    orders_discount_applied.mapped("bonus_order")
                )

            # [>] Calculate total discount money from different sources
            total_amount_discount_approved = sum(
                partner.compute_discount_line_ids.filtered(
                    lambda r: r.state == "done"
                ).mapped("total_money")
            ) + sum(
                partner.compute_warranty_discount_line_ids.filtered(
                    lambda r: r.parent_state == "done"
                ).mapped("total_amount_currency")
            )

            # [>] Update 'amount' and 'amount_currency' fields
            wallet = total_amount_discount_approved - partner.total_so_bonus_order
            partner.amount = partner.amount_currency = wallet if wallet > 0 else 0.0

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
                                   If not provided, defaults to 100.

        Returns:
            bool: True if the task completed successfully, False otherwise.
        """
        records_limit = limit if limit else 100
        try:
            agency_partners = (
                self.env["res.partner"]
                .sudo()
                .search([("is_agency", "=", True)], limit=records_limit)
            )
            for partner in agency_partners:
                partner.with_context(
                    cron_service_run=True
                ).action_update_discount_amount()
            _logger.info(f"Recomputed discount for {len(partners)} partner agencies.")
            return True
        except Exception as e:
            _logger.error(f"Failed to recompute discount for partner agencies: {e}")
            return False
