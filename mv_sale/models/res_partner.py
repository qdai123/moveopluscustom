# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = "res.partner"

    def name_get(self):
        res = []
        for partner in self:
            res.append((partner.id, partner.partner_agency_name))
        return res

    @api.model
    def auto_update_data(self):
        for record in self.filtered("is_agency"):
            # Calculate total discount money from different sources
            total_amount_discount_approved, total_amount_discount_waiting_approve = (
                self._calculate_total_discounts(record)
            )

            # Calculate wallet amount
            wallet = total_amount_discount_approved - record.total_so_bonus_order
            record.amount = record.amount_currency = wallet if wallet > 0 else 0.0
            record.waiting_amount_currency = total_amount_discount_waiting_approve

    # === TRƯỜNG CƠ SỞ DỮ LIỆU
    # line_ids: Nội dung chi tiết chiết khấu được áp dụng cho Đại Lý
    # amount/amount_currency: Ví tiền được chiết khấu cho Đại lý sử dụng
    # waiting_amount_currency: Ví tiền chờ duyệt
    # sale_mv_ids: Danh sách các đơn hàng mà Đại Lý đã được áp dụng chiết khấu
    # total_so_bonus_order: Tổng số tiền chiết khấu đã được áp dụng cho các đơn hàng của Đại Lý
    # total_so_quotations_discount: Tổng số tiền chiết khấu đang chờ xác nhận cho các đơn báo giá của Đại Lý
    # ===#
    line_ids = fields.One2many("mv.discount.partner", "partner_id", copy=False)
    currency_id = fields.Many2one(
        "res.currency", compute="_get_company_currency", readonly=True
    )
    amount = fields.Float(readonly=True)
    amount_currency = fields.Monetary(currency_field="currency_id", readonly=True)
    waiting_amount_currency = fields.Monetary(
        currency_field="currency_id", readonly=True
    )
    sale_mv_ids = fields.Many2many("sale.order", readonly=True)
    total_so_bonus_order = fields.Monetary(compute="_compute_sale_order", store=True)
    total_so_quotations_discount = fields.Monetary(
        compute="_compute_sale_order", store=True
    )

    # === THÔNG TIN ĐẠI LÝ
    # Đại lý: Là nhà phân phối trực thuộc của công ty MOVEOPLUS
    # Đại lý Vùng Trắng (White Agency): Đại lý phân phối sản phẩm tại các vùng trắng
    # Đại lý Miền Nam (Southern Agency): Đại lý phân phối sản phẩm tại miền Nam
    # Bảo lãnh ngân hàng, Chiết khấu bảo lãnh ngân hàng (%)
    # ===#
    partner_agency_name = fields.Char(
        "Tên Đại Lý", compute="_compute_partner_agency_name", store=True
    )
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
    # BUSINESS Methods
    # =================================

    def action_update_discount_amount(self):
        """
        Update the discount amount for partner agencies.

        This method processes orders with discounts applied, calculates the total discount
        money from different sources, and updates the wallet amount for each partner agency.

        :return: dict: A success notification if triggered manually, otherwise None.
        """
        _logger.debug("Starting 'action_update_discount_amount'.")

        for record in self.filtered("is_agency"):
            # Initialize discount-related fields
            record.sale_mv_ids = None
            record.total_so_bonus_order = 0
            record.total_so_quotations_discount = 0
            record.amount = record.amount_currency = 0

            # Process orders with discounts applied and in 'sale' state
            orders_discount_applied = self._get_orders_with_discount(record, "sale")
            if orders_discount_applied:
                self._process_orders_with_discount(record, orders_discount_applied)

            # Process orders with discounts applied and not in 'sale' state and not 'cancel'
            quotations_discount_applying = self._get_orders_with_discount(
                record, "not_sale"
            )
            if quotations_discount_applying:
                self._process_orders_with_discount(
                    record, quotations_discount_applying, is_sale=False
                )

            # Calculate total discount money from different sources
            total_amount_discount_approved, total_amount_discount_waiting_approve = (
                self._calculate_total_discounts(record)
            )

            # Calculate wallet amount
            wallet = total_amount_discount_approved - record.total_so_bonus_order
            record.amount = record.amount_currency = wallet if wallet > 0 else 0.0
            record.waiting_amount_currency = total_amount_discount_waiting_approve

            # Auto update data
            self.auto_update_data()

            # Trigger update manual notification if context is set
            if self.env.context.get("trigger_manual_update", False):
                _logger.debug(
                    "Manual update triggered, returning success notification."
                )
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

        _logger.debug("Completed 'action_update_discount_amount'.")

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

    @api.depends("name", "is_agency", "is_white_agency", "is_southern_agency")
    def _compute_partner_agency_name(self):
        """
        Compute the agency name for each partner based on their agency type.

        This method constructs the agency name by appending the agency type
        (White Agency or Southern Agency) to the partner's name.

        :return: None
        """
        _logger.debug("Starting '_compute_partner_agency_name' computation.")

        for partner in self.filtered("is_agency"):
            try:
                path_agency = "Đại lý"
                if partner.is_white_agency:
                    path_agency += " Vùng Trắng"
                elif partner.is_southern_agency:
                    path_agency += " Miền Nam"
                partner.partner_agency_name = f"{partner.name} / {path_agency}"
                _logger.debug(
                    f"Computed agency name for partner {partner.id}: {partner.partner_agency_name}"
                )
            except Exception as e:
                _logger.error(
                    f"Error computing agency name for partner {partner.id}: {e}"
                )
                partner.partner_agency_name = partner.name

        _logger.debug("Completed '_compute_partner_agency_name' computation.")

    @api.depends("sale_order_ids")
    def _compute_sale_order(self):
        """
        Compute the sale order details for the partner, including discounts and wallet amounts.
        """
        _logger.debug("Starting '_compute_sale_order' computation.")

        for record in self:
            record.sale_mv_ids = None
            record.total_so_bonus_order = 0
            record.total_so_quotations_discount = 0
            record.amount = record.amount_currency = 0

            # Process orders with discounts applied and in 'sale' state
            orders_discount_applied = self._get_orders_with_discount(record, "sale")
            if orders_discount_applied:
                self._process_orders_with_discount(record, orders_discount_applied)

            # Process orders with discounts applied and not in 'sale' state and not 'cancel'
            quotations_discount_applying = self._get_orders_with_discount(
                record, "not_sale"
            )
            if quotations_discount_applying:
                self._process_orders_with_discount(
                    record, quotations_discount_applying, is_sale=False
                )

            # Calculate total discount money from different sources
            total_amount_discount_approved, total_amount_discount_waiting_approve = (
                self._calculate_total_discounts(record)
            )

            # Calculate wallet amount
            wallet = (
                total_amount_discount_approved
                - total_amount_discount_waiting_approve
                - record.total_so_bonus_order
            )
            record.amount = record.amount_currency = wallet if wallet > 0 else 0.0
            record.waiting_amount_currency = total_amount_discount_waiting_approve

        _logger.debug("Completed '_compute_sale_order' computation.")

    def _get_orders_with_discount(self, record, state):
        """
        Get orders with discounts applied based on the state.

        :param record: The current partner record.
        :param state: The state of the orders to filter ('sale' or 'not_sale').
        :return: Filtered orders with discounts applied.
        """
        if state == "sale":
            return record.sale_order_ids.filtered(
                lambda order: order.state == "sale"
                and (
                    order.discount_agency_set
                    or order.order_line._filter_discount_agency_lines(order)
                )
            )
        else:
            return record.sale_order_ids.filtered(
                lambda order: order.state not in ["sale", "cancel"]
                and (
                    order.discount_agency_set
                    or order.order_line._filter_discount_agency_lines(order)
                )
            )

    def _process_orders_with_discount(self, record, orders, is_sale=True):
        """
        Process orders with discounts applied.

        :param record: The current partner record.
        :param orders: The orders to process.
        :param is_sale: Boolean indicating if the orders are in 'sale' state.
        """
        orders._compute_partner_bonus()
        if is_sale:
            record.sale_mv_ids = [(6, 0, orders.ids)]
            record.total_so_bonus_order = sum(orders.mapped("bonus_order"))
        else:
            record.total_so_quotations_discount = sum(orders.mapped("bonus_order"))

    def _calculate_total_discounts(self, record):
        """
        Calculate total discount money from different sources.

        :param record: The current partner record.
        :return: Tuple containing total approved discounts and total waiting approval discounts.
        """
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
        total_amount_discount_waiting_approve = sum(
            line.total_money
            for line in record.compute_discount_line_ids.filtered(
                lambda r: r.state != "done"
            )
        ) + sum(
            line.total_amount_currency
            for line in record.compute_warranty_discount_line_ids.filtered(
                lambda r: r.parent_state != "done"
            )
        )
        return total_amount_discount_approved, total_amount_discount_waiting_approve

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
        _logger.debug("Starting '_cron_recompute_partner_discount'.")

        records_limit = limit if limit else 100
        try:
            agency_partners = self._get_agency_partners(records_limit)
            for partner in agency_partners:
                partner.with_context(
                    cron_service_run=True
                ).action_update_discount_amount()
            _logger.info(
                f"Recomputed discount for {len(agency_partners)} partner agencies."
            )
            return True
        except Exception as e:
            _logger.error(f"Failed to recompute discount for partner agencies: {e}")
            return False

    def _get_agency_partners(self, limit):
        """
        Retrieve agency partners up to the specified limit.

        Args:
            limit (int): The maximum number of partners to retrieve.

        Returns:
            recordset: The retrieved agency partners.
        """
        return (
            self.env["res.partner"]
            .sudo()
            .search([("is_agency", "=", True)], limit=limit)
        )
