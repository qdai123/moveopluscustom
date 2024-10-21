# -*- coding: utf-8 -*-
import logging

from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# GROUPS ACCESS:
GROUP_COMPUTE_DISCOUNT_APPROVER = "mv_sale.group_mv_compute_discount_approver"


def get_last_date_of_month(first_date):
    # Calculate the first day of the next month, then subtract one day
    last_date = first_date + relativedelta(months=1) - relativedelta(days=1)
    return last_date


class ResPartner(models.Model):
    _inherit = "res.partner"

    # === TRƯỜNG CƠ SỞ DỮ LIỆU
    # line_ids: Nội dung chi tiết chiết khấu được áp dụng cho Đại Lý
    # amount/amount_currency: Ví tiền được chiết khấu cho Đại lý sử dụng
    # waiting_amount_currency: Ví tiền chờ duyệt
    # sale_mv_ids: Danh sách các đơn hàng mà Đại Lý đã được áp dụng chiết khấu
    # total_so_bonus_order: Tổng số tiền chiết khấu đã được áp dụng cho các đơn hàng của Đại Lý
    # total_so_quotations_discount: Tổng số tiền chiết khấu đang chờ xác nhận cho các đơn báo giá của Đại Lý
    # use_for_report: Sử dụng trong Báo Cáo
    # ===#
    line_ids = fields.One2many(
        "mv.discount.partner",
        "partner_id",
        copy=False,
    )
    currency_id = fields.Many2one(
        "res.currency",
        compute="_get_company_currency",
        readonly=True,
    )
    amount = fields.Float(readonly=True)
    amount_currency = fields.Monetary(currency_field="currency_id", readonly=True)
    quantity_threshold_value = fields.Integer(
        string="Quantity Threshold Value",
        default=4,
        help="Set the quantity threshold value for this partner.",
    )
    waiting_amount_currency = fields.Monetary(
        currency_field="currency_id",
        readonly=True,
    )
    sale_mv_ids = fields.Many2many("sale.order", readonly=True)
    total_so_bonus_order = fields.Monetary(compute="_compute_sale_order", store=True)
    total_so_quotations_discount = fields.Monetary(
        compute="_compute_sale_order", store=True
    )
    use_for_report = fields.Boolean("Sử dụng trong Báo Cáo", default=False)

    # === THÔNG TIN ĐẠI LÝ
    # Đại lý: Là nhà phân phối trực thuộc của công ty MOVEOPLUS
    # Đại lý Vùng Trắng (White Agency): Đại lý phân phối sản phẩm tại các vùng trắng
    # Đại lý Miền Nam (Southern Agency): Đại lý phân phối sản phẩm tại miền Nam
    # Bảo lãnh ngân hàng, Chiết khấu bảo lãnh ngân hàng (%)
    # ===#
    partner_agency_name = fields.Char(
        "Tên Đại Lý",
        compute="_compute_partner_agency_name",
        store=True,
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

    # === MO+ POLICY: CHÍNH SÁCH CHIẾT KHẤU GIẢM GIÁ ===#
    discount_policy_ids = fields.Many2many(
        "mv.discount.policy",
        "mv_discount_policy_res_partner_rel",
        "mv_discount_policy_id",
        "partner_id",
        string="Chiết khấu giảm giá",
        help="Chính sách 'CHIẾT KHẤU GIẢM GIÁ' cho Đại Lý",
    )
    compute_discount_policy_line_ids = fields.One2many(
        "mv.compute.discount.policy.line",
        "partner_id",
        string="Chi tiết: CHIẾT KHẤU GIẢM GIÁ",
        domain=[("parent_id", "!=", False)],
    )

    # === MO+ POLICY: CHÍNH SÁCH CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH ===#
    warranty_discount_policy_ids = fields.Many2many(
        "mv.warranty.discount.policy",
        string="Chiết khấu kích hoạt bảo hành",
        help="Chính sách 'CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH' cho Đại Lý",
    )
    compute_warranty_discount_line_ids = fields.One2many(
        "mv.compute.warranty.discount.policy.line",
        "partner_id",
        "Chi tiết: CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH",
        domain=[("parent_id", "!=", False)],
    )

    # === MO+ POLICY: CHÍNH SÁCH CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH THEO SẢN PHẨM ===#
    discount_product_warranty_policy_ids = fields.Many2many(
        "mv.discount.product.warranty.policy",
        string="Chiết khấu kích hoạt theo sản phẩm",
        help="Chính sách 'CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH THEO SẢN PHẨM' cho Đại Lý",
    )
    compute_discount_product_warranty_line_ids = fields.One2many(
        "mv.compute.discount.product.warranty.policy.line",
        "partner_id",
        "Chi tiết: CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH THEO SẢN PHẨM",
        domain=[("parent_id", "!=", False)],
    )

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

            # Re-update data 'sale_mv_ids'
            orders_discount_applied = self._get_orders_with_discount(record, "sale")
            record.sale_mv_ids = [
                (6, 0, orders_discount_applied.ids if orders_discount_applied else [])
            ]

    @api.model
    def get_discount_history(self, partner_id):
        if not partner_id:
            return []

        domain = [("partner_id", "=", partner_id)]
        order_by = "create_date desc"

        discount_history_records = self.env["mv.discount.partner.history"].search(
            domain, order=order_by
        )

        return discount_history_records

    @api.model
    def get_total_discount_history(self, partner):
        if not partner:
            return []

        return self.env["mv.partner.total.discount.detail.history"].search_fetch(
            domain=[
                ("partner_id", "in", partner.ids),
                (
                    "policy_line_id",
                    "in",
                    partner.mapped("compute_discount_line_ids").ids,
                ),
            ],
            field_names=[
                "parent_id",
                "policy_line_id",
                "partner_id",
                "description",
                "total_discount_amount_display",
                "total_discount_amount",
            ],
            order="create_date desc",
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

        for partner in self:
            # Initialize discount-related fields
            partner.sale_mv_ids = None
            partner.amount = 0
            partner.amount_currency = 0

            # Process orders with discounts applied and in 'sale' state
            orders_discount_applied = self._get_orders_with_discount(partner, "sale")
            if orders_discount_applied:
                total_so_bonus_order = self._process_orders_with_discount(
                    partner, orders_discount_applied, is_sale=True
                )
                partner.total_so_bonus_order = total_so_bonus_order
            else:
                partner.total_so_bonus_order = 0

            # Process orders with discounts applied and not in 'sale' state and not 'cancel'
            quotations_discount_applying = self._get_orders_with_discount(
                partner, "not_sale"
            )
            if quotations_discount_applying:
                total_so_quotations_discount = self._process_orders_with_discount(
                    partner, quotations_discount_applying, is_sale=False
                )
                partner.total_so_quotations_discount = total_so_quotations_discount
            else:
                partner.total_so_quotations_discount = 0

            # Calculate total discount money from different sources
            total_amount_discount_approved, total_amount_discount_waiting_approve = (
                self._calculate_total_discounts(partner)
            )
            partner.waiting_amount_currency = total_amount_discount_waiting_approve

            # Calculate wallet amount
            wallet = total_amount_discount_approved - partner.total_so_bonus_order
            partner.amount = wallet if wallet > 0 else 0.0
            partner.amount_currency = wallet if wallet > 0 else 0.0

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

        for partner in self:
            partner.sale_mv_ids = None
            partner.amount = 0
            partner.amount_currency = 0

            # Process orders with discounts applied and in 'sale' state
            orders_discount_applied = self._get_orders_with_discount(partner, "sale")
            if orders_discount_applied:
                total_so_bonus_order = self._process_orders_with_discount(
                    partner, orders_discount_applied, is_sale=True
                )
                partner.total_so_bonus_order = total_so_bonus_order
            else:
                partner.total_so_bonus_order = 0

            # Process orders with discounts applied and not in 'sale' state and not 'cancel'
            quotations_discount_applying = self._get_orders_with_discount(
                partner, "not_sale"
            )
            if quotations_discount_applying:
                total_so_quotations_discount = self._process_orders_with_discount(
                    partner, quotations_discount_applying, is_sale=False
                )
                partner.total_so_quotations_discount = total_so_quotations_discount
            else:
                partner.total_so_quotations_discount = 0

            # Calculate total discount money from different sources
            total_amount_discount_approved, total_amount_discount_waiting_approve = (
                self._calculate_total_discounts(partner)
            )
            partner.waiting_amount_currency = total_amount_discount_waiting_approve

            # Calculate wallet amount
            wallet = total_amount_discount_approved - partner.total_so_bonus_order
            partner.amount = wallet if wallet > 0 else 0.0
            partner.amount_currency = wallet if wallet > 0 else 0.0

        _logger.debug("Completed '_compute_sale_order' computation.")

    def _get_orders_with_discount(self, partner, state):
        """
        Get orders with discounts applied based on the state.

        :param record: The current partner record.
        :param state: The state of the orders to filter ('sale' or 'not_sale').
        :return: Filtered orders with discounts applied.
        """
        Order = self.env["sale.order"]
        agency_domain = [("partner_id", "=", partner.id)]
        if state == "sale":
            agency_domain += [("state", "=", "sale")]
            return Order.search(agency_domain).filtered(
                lambda order: order.order_line._filter_agency_lines(order)
                or order.bonus_order > 0
            )
        elif state == "not_sale":
            agency_domain += [("state", "in", ["draft", "sent"])]
            return Order.search(agency_domain).filtered(
                lambda order: order.order_line._filter_agency_lines(order)
                or order.bonus_order > 0
            )

    def _process_orders_with_discount(self, record, orders, is_sale=True):
        """
        Process orders with discounts applied.

        :param record: The current partner record.
        :param orders: The orders to process.
        :param is_sale: Boolean indicating if the orders are in 'sale' state.
        """
        orders._compute_partner_bonus()
        orders._compute_bonus_order_line()
        total = sum(orders.mapped("bonus_order"))
        if is_sale:
            record.sale_mv_ids = [(6, 0, orders.ids)]

        return total

    def _calculate_total_discounts(self, record):
        """
        Calculate total discount money from different sources.

        :param record: The current partner record.
        :return: Tuple containing total approved discounts and total waiting approval discounts.
        """
        total_amount_discount_approved = (
            sum(
                line.total_money
                for line in record.compute_discount_line_ids.filtered(
                    lambda r: r.state == "done"
                )
            )
            + sum(
                line.total_amount_currency
                for line in record.compute_warranty_discount_line_ids.filtered(
                    lambda r: r.parent_state == "done"
                )
            )
            + sum(
                line.total_price_discount
                for line in record.compute_discount_policy_line_ids.filtered(
                    lambda r: r.state == "done"
                )
            )
            + sum(
                line.total_reward_amount
                for line in record.compute_discount_product_warranty_line_ids.filtered(
                    lambda r: r.state == "done"
                )
            )
        )
        total_amount_discount_waiting_approve = (
            sum(
                line.total_money
                for line in record.compute_discount_line_ids.filtered(
                    lambda r: r.state != "done"
                )
            )
            + sum(
                line.total_amount_currency
                for line in record.compute_warranty_discount_line_ids.filtered(
                    lambda r: r.parent_state != "done"
                )
            )
            + sum(
                line.total_price_discount
                for line in record.compute_discount_policy_line_ids.filtered(
                    lambda r: r.state != "done"
                )
            )
            + sum(
                line.total_reward_amount
                for line in record.compute_discount_product_warranty_line_ids.filtered(
                    lambda r: r.state != "done"
                )
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

    # =================================
    # ACTION Methods
    # =================================

    def action_activation_for_agency(self):
        for partner in self:
            partner.write({"is_agency": True})

    def action_update_discount_amount_for_wallet(self):
        self.ensure_one()
        # TODO: Action Update Discount Amount for Wallet - Phat Dang <phat.dangminh@moveoplus.com>
        return True

    def action_view_partner_discount_history(self):
        self.ensure_one()
        return {
            "name": f"Lịch sử chiết khấu Đại lý: {self.name}",
            "type": "ir.actions.act_window",
            "res_model": "mv.discount.partner.history",
            "view_mode": "tree",
            "views": [
                [
                    self.env.ref("mv_sale.mv_discount_partner_history_view_tree").id,
                    "tree",
                ]
            ],
            "domain": [("partner_id", "=", self.id)],
            "context": {"default_partner_id": self.id},
        }

    # ==================================
    # HISTORY HANDLER Methods
    # ==================================

    @api.model
    def generate_all_partner_discount_histories(self):
        for partner in self:
            if partner and partner.is_agency:
                partner.generate_partner_discount_histories()

    def generate_partner_discount_histories(self):
        """
        Generate discount history lines for the partner.

        This method retrieves all bonus orders, production policy discounts, and warranty policy discounts
        for the partner and creates corresponding history lines.

        :return: list: Created history lines.
        """
        self.ensure_one()

        if not self.is_agency:
            return

        partner = self
        keys_list = []
        vals_list = []

        base_histories = self.env["mv.discount.partner.history"].search(
            [("partner_id", "=", self.id)]
        )
        base_order_discount_histories = base_histories.mapped("sale_order_id")
        base_production_discount_histories = base_histories.mapped(
            "production_discount_policy_id"
        )
        base_warranty_discount_histories = base_histories.mapped(
            "warranty_discount_policy_id"
        )

        # ||| Generate history lines for Sale Order Discounts
        order_discount = self._get_orders_with_discount(
            partner.filtered("is_agency"), "sale"
        )
        for order in order_discount:
            if order.id not in base_order_discount_histories.ids:
                keys_list.append(f"{order.date_order.month}_{order.date_order.year}")
                vals_list.append(
                    {
                        f"{order.date_order.month}_{order.date_order.year}": self._prepare_history_line_vals(
                            order,
                            "sale",
                            f"Đơn {order.name} đã được xác nhận, đã khấu trừ tiền chiết khấu của Đại lý.",
                            order.bonus_order,
                        )
                    }
                )

        # ||| Generate history lines for production policy discounts
        for record_line in partner.compute_discount_line_ids.filtered(
            lambda r: r.state == "done"
            and r.id not in base_production_discount_histories.ids
        ):
            data_key = f"{record_line.parent_id.report_date.month}_{record_line.parent_id.report_date.year}"
            keys_list.append(data_key)
            vals_list.append(
                {
                    data_key: self._prepare_history_line_vals(
                        record_line,
                        "done",
                        f"Chiết khấu sản lượng tháng {record_line.name} đã được duyệt cho Đại lý.",
                        record_line.total_money,
                    )
                }
            )

        # ||| Generate history lines for warranty policy discounts
        for record_line in partner.compute_warranty_discount_line_ids.filtered(
            lambda r: r.parent_state == "done"
            and r.id not in base_warranty_discount_histories.ids
        ):
            data_key = f"{record_line.parent_id.compute_date.month}_{record_line.parent_id.compute_date.year}"
            keys_list.append(data_key)
            vals_list.append(
                {
                    data_key: self._prepare_history_line_vals(
                        record_line,
                        "done",
                        f"Chiết khấu kích hoạt bảo hành tháng {record_line.parent_name} đã được duyệt cho Đại lý.",
                        record_line.total_amount_currency,
                    )
                }
            )

        history_env = self.env["mv.discount.partner.history"].sudo()
        keys_list = sorted(list(set(keys_list)), reverse=True)
        vals_list = sorted(vals_list, key=lambda val: val.keys(), reverse=True)
        if keys_list and vals_list:
            for key in keys_list:
                for vals in vals_list:
                    if key in vals:
                        vals = vals[key]
                        history_env.create(vals)

    def _prepare_history_line_vals(self, record, state, description, total_money):
        """
        Prepare the values for creating a history line.

        :param record: The record data discount.
        :param state: The state of record data discount.
        :param description: The description of the discount.
        :return: dict: The values for creating a history line.
        """
        is_positive_money = False
        is_negative_money = False
        total_money_display = "{:,.2f}".format(total_money)
        history_date = record.write_date
        history_user_action_id = record.write_uid.id

        # ||| Sale Order
        if state == "sale":
            is_negative_money = total_money > 0
            total_money_display = (
                "- " + total_money_display if total_money > 0 else total_money_display
            )
            history_date = record.date_order or record.write_date
            history_user_action_id = record.user_id.id or record.write_uid.id

        # ||| Production Policy & Warranty Policy
        if state == "done":
            is_positive_money = total_money > 0
            total_money_display = (
                "+ " + total_money_display if total_money > 0 else total_money_display
            )
            history_date = record.parent_id.approved_date or record.parent_id.write_date
            users_can_approve_compute_discount = (
                self.env["res.users"]
                .sudo()
                .get_users_from_group(
                    self.env["ir.model.data"]._xmlid_to_res_id(
                        GROUP_COMPUTE_DISCOUNT_APPROVER
                    )
                )
            )
            users_can_approve_compute_discount = [
                uid for uid in users_can_approve_compute_discount if uid not in [1, 2]
            ]
            history_user_action_id = users_can_approve_compute_discount[0] or False

        return {
            "partner_id": record.partner_id.id,
            "history_date": history_date,
            "history_user_action_id": history_user_action_id,
            "history_description": description,
            "sale_order_id": record.id if state == "sale" else False,
            "sale_order_state": record.state if state == "sale" else None,
            "sale_order_discount_money_apply": (
                total_money if record._name == "sale.order" else 0
            ),
            "production_discount_policy_id": (
                record.id if record._name == "mv.compute.discount.line" else False
            ),
            "production_discount_policy_total_money": (
                total_money if record._name == "mv.compute.discount.line" else 0
            ),
            "warranty_discount_policy_id": (
                record.id
                if record._name == "mv.compute.warranty.discount.policy.line"
                else False
            ),
            "warranty_discount_policy_total_money": (
                total_money
                if record._name == "mv.compute.warranty.discount.policy.line"
                else 0
            ),
            "total_money": total_money,
            "total_money_discount_display": total_money_display,
            "is_waiting_approval": False,
            "is_positive_money": is_positive_money,
            "is_negative_money": is_negative_money,
        }

    # ==================================
    # CRON SERVICE Methods
    # ==================================

    @api.model
    def _cron_recompute_partner_discount(self, limit=None):
        limited_records = limit if limit else 100
        for partner in self.env["res.partner"].search(
            [("is_agency", "=", True)], limit=limited_records
        ):
            partner.with_context(cron_service_run=True).action_update_discount_amount()
