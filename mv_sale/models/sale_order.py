# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

TARGET_CATEGORY_ID = 19
DISCOUNT_PERCENTAGE_DIVISOR = 100
DISCOUNT_QUANTITY_THRESHOLD = 10
QUANTITY_THRESHOLD = 4

GROUP_SALES_MANAGER = "sales_team.group_sale_manager"
GROUP_SALES_ALL = "sales_team.group_sale_salesman_all_leads"
GROUP_SALESPERSON = "sales_team.group_sale_salesman"


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # === BASE FIELDS ===#
    is_sales_manager = fields.Boolean(compute="_compute_permissions")
    discount_agency_set = fields.Boolean(
        compute="_compute_permissions",
        help="""Ghi nhận: Khi có bổ sung "Chiết khấu sản lượng (Tháng/Quý/Năm)" trên đơn bán.""",
    )
    compute_discount_agency = fields.Boolean(compute="_compute_permissions")
    recompute_discount_agency = fields.Boolean(
        compute="_compute_permissions",
        string="Discount Agency Amount should be recomputed",
    )
    is_order_returns = fields.Boolean(
        default=False, help="Ghi nhận: Là đơn đổi/trả hàng."
    )  # TODO: Needs study cases for SO Returns
    date_invoice = fields.Datetime(readonly=True)
    quantity_change = fields.Float(readonly=True)

    # === PARTNER FIELDS ===#
    partner_agency = fields.Boolean(
        related="partner_id.is_agency", store=True, readonly=True
    )
    partner_white_agency = fields.Boolean(
        related="partner_id.is_white_agency", store=True, readonly=True
    )
    partner_southern_agency = fields.Boolean(
        related="partner_id.is_southern_agency", store=True, readonly=True
    )
    bank_guarantee = fields.Boolean(
        related="partner_id.bank_guarantee", store=True, readonly=True
    )
    discount_bank_guarantee = fields.Float(compute="_compute_discount", store=True)
    after_discount_bank_guarantee = fields.Float(
        compute="_compute_discount", store=True
    )

    # === DISCOUNT POLICY FIELDS ===#
    discount_line_id = fields.Many2one("mv.compute.discount.line", readonly=True)
    check_discount_10 = fields.Boolean(compute="_compute_discount", store=True)
    percentage = fields.Float(compute="_compute_discount", store=True)
    bonus_max = fields.Float(
        compute="_compute_bonus_order_line",
        store=True,
        help="Số tiền tối đa mà Đại lý có thể áp dụng để tính chiết khấu.",
    )
    bonus_order = fields.Float(
        compute="_compute_bonus_order_line",
        store=True,
        help="Số tiền chiết khấu đã và đang áp dụng trên đơn bán.",
    )
    bonus_remaining = fields.Float(
        compute="_compute_partner_bonus",
        store=True,
        help="Số tiền Đại lý có thể áp dụng để tính chiết khấu.",
    )

    @api.depends("state", "order_line.product_id", "order_line.product_uom_qty")
    @api.depends_context("uid")
    def _compute_permissions(self):
        """
        Compute permissions for each sale order based on the user's role and order state.

        This method checks if the user is a Sales Manager, if the order has discount agency lines,
        and if the order is in a state where discount agency can be computed or should be recomputed.

        :return: None
        """
        _logger.debug("Starting '_compute_permissions' computation.")

        for order in self:
            try:
                # Check if the user is a Sales Manager
                order.is_sales_manager = self.env.user.has_group(GROUP_SALES_MANAGER)
                # Check if the order has discount agency lines
                order.discount_agency_set = (
                    order.order_line._filter_discount_agency_lines(order)
                )
                _logger.debug(
                    f"Order {order.id}: discount_agency_set = {order.discount_agency_set}"
                )
                # Check if the order is in a state where discount agency can be computed
                order.compute_discount_agency = (
                    order.state in ["draft", "sent"]
                    and not order.discount_agency_set
                    and order.partner_agency
                )
                # Check if the order is in a state where discount agency should be recomputed
                order.recompute_discount_agency = (
                    order.state in ["draft", "sent"]
                    and order.discount_agency_set
                    and order.partner_agency
                )

            except Exception as e:
                _logger.error(f"Error computing permissions for order {order.id}: {e}")
                order.is_sales_manager = False
                order.discount_agency_set = False
                order.compute_discount_agency = False
                order.recompute_discount_agency = False

        _logger.debug("Completed '_compute_permissions' computation.")

    def _compute_partner_bonus(self):
        for order in self.filtered("partner_agency"):
            if order.state == "cancel" or not order.partner_agency:
                order.bonus_remaining = 0
                continue

            partner_wallet = order.partner_id.amount_currency
            bonus_order_line = order.order_line._get_discount_agency_line()

            if bonus_order_line:
                bonus_order = abs(bonus_order_line[0].sudo().price_unit)
                remaining_bonus = partner_wallet - bonus_order
                order.bonus_remaining = remaining_bonus if remaining_bonus > 0 else 0
            else:
                order.bonus_remaining = partner_wallet

    @api.depends("state", "order_line.product_id")
    def _compute_bonus_order_line(self):
        for order in self.filtered("partner_agency"):
            if order.state != "cancel" and order.order_line:
                bonus_order_line = order.order_line._get_discount_agency_line()
                if bonus_order_line:
                    order.bonus_order = abs(bonus_order_line[0].sudo().price_unit)
                else:
                    order.bonus_order = 0

                order.bonus_max = (
                    order.total_price_no_service
                    - order.total_price_discount
                    - order.total_price_discount_10
                    - order.discount_bank_guarantee
                ) / 2
            else:
                order.bonus_order = 0
                order.bonus_max = 0

    # === AMOUNT/TOTAL FIELDS ===#
    total_price_no_service = fields.Float(
        compute="_compute_discount",
        store=True,
        help="Total price without Product Service, No Discount, No Tax",
    )
    total_price_discount = fields.Float(
        compute="_compute_discount",
        store=True,
        help="Total price discount without Product Service, No Tax",
    )
    total_price_after_discount = fields.Float(
        compute="_compute_discount",
        store=True,
        help="Total price after discount without Product Service, No Tax",
    )
    total_price_discount_10 = fields.Float(
        compute="_compute_discount",
        help="Total price discount 1% when [product_uom_qty] >= 10",
        store=True,
    )
    total_price_after_discount_10 = fields.Float(
        compute="_compute_discount",
        store=True,
        help="Total price after discount 1% when [product_uom_qty] >= 10",
    )
    total_price_after_discount_month = fields.Float(
        compute="_compute_discount",
        store=True,
        help="Total price after discount for a month",
    )

    def check_category_product(self, categ_id):
        """
        Check if the given product category or any of its parent categories have an ID of TARGET_CATEGORY_ID.

        Args:
            categ_id (models.Model): The product category to check.

        Returns:
            bool: True if the product category
            or any of its parent categories have an ID of TARGET_CATEGORY_ID, False otherwise.
        """
        try:
            if categ_id.id == TARGET_CATEGORY_ID:
                return True
            if categ_id.parent_id:
                return self.check_category_product(categ_id.parent_id)
        except AttributeError as e:
            _logger.error("Failed to check category product: %s", e)
            return False
        return False

    def _get_order_lines_to_report(self):
        Orders = super(SaleOrder, self)._get_order_lines_to_report()
        return Orders.sorted(
            key=lambda order: order.product_id.product_tmpl_id.detailed_type
        )

    # ==================================

    @api.depends("order_line", "order_line.product_id", "order_line.product_uom_qty")
    def _compute_discount(self):
        for order in self:
            # Trả về mặc định các giá trị gốc
            order.percentage = 0
            order.check_discount_10 = False
            order.total_price_no_service = 0
            order.total_price_discount = 0
            order.total_price_after_discount = 0
            order.total_price_discount_10 = 0
            order.total_price_after_discount_10 = 0
            order.total_price_after_discount_month = 0
            order.discount_bank_guarantee = 0
            order.after_discount_bank_guarantee = 0

            # [!] Kiểm tra có phải Đại lý trực thuộc của MOVEO+ hay không?
            partner_agency = order.partner_id.is_agency

            # TODO: Do không còn áp dụng cách tính cũ, nên cần check lại toàn bộ phần tính toán theo số lượng 10 lốp này
            # [!] Kiểm tra xem thỏa điều kiện để mua đủ trên 10 lốp xe continental
            order.check_discount_10 = (
                order.check_discount_applicable() if partner_agency else False
            )

            # [!] Tính tổng tiền giá sản phẩm không bao gồm hàng Dịch Vụ,
            #      tính giá gốc ban đầu, không bao gồm Thuế
            order.calculate_discount_values()

            # [!] Nếu không còn dòng sản phẩm nào thì xóa hết các dòng chiết khấu bao gồm cả phương thức giao hàng
            order.handle_discount_lines()

    def check_discount_applicable(self):
        order_lines = self.order_line.filtered(
            lambda sol: self.check_category_product(sol.product_id.categ_id)
            and sol.product_id.product_tmpl_id.detailed_type == "product"
        )
        return (
            len(order_lines) >= 1
            and sum(order_lines.mapped("product_uom_qty"))
            >= DISCOUNT_QUANTITY_THRESHOLD
        )

    def calculate_discount_values(self):
        order = self
        product_discount_percentage = 0
        total_price_no_service = 0
        total_price_discount = 0

        order_product_lines = order.order_line.filtered(
            lambda sol: sol.product_id.product_tmpl_id.detailed_type == "product"
        )
        for line in order_product_lines:
            total_price_no_service += line.price_unit * line.product_uom_qty
            total_price_discount += (
                line.price_unit
                * line.product_uom_qty
                * line.discount
                / DISCOUNT_PERCENTAGE_DIVISOR
            )
            product_discount_percentage = line.discount

        order.percentage = product_discount_percentage
        order.total_price_no_service = total_price_no_service
        order.total_price_discount = total_price_discount
        order.total_price_after_discount = (
            order.total_price_no_service - order.total_price_discount
        )
        order.total_price_discount_10 = (
            order.total_price_after_discount / DISCOUNT_PERCENTAGE_DIVISOR
        )

        # [>] Tính Chiết Khấu Bảo Lãnh Ngân Hàng
        if order.bank_guarantee:
            order.discount_bank_guarantee = (
                order.total_price_after_discount
                * order.partner_id.discount_bank_guarantee
                / DISCOUNT_PERCENTAGE_DIVISOR
            )
            if order.discount_bank_guarantee > 0:
                order.with_context(bank_guarantee=True).create_discount_bank_guarantee()

        order.after_discount_bank_guarantee = (
            order.total_price_after_discount - order.discount_bank_guarantee
        )
        order.total_price_after_discount_10 = (
            order.after_discount_bank_guarantee - order.total_price_discount_10
        )
        order.total_price_after_discount_month = (
            order.total_price_after_discount_10 - order.bonus_order
        )

    def handle_discount_lines(self):
        """
        Removes discount lines from the order if there are no more products in the order.
        Specifically, it checks for the existence of order lines with provided product codes
        and removes them if there are no more products in the order.
        """
        discount_product_codes = {"CKT", "CKBL"}
        if self.partner_white_agency:
            discount_product_codes.add("CKSLVT")  # CKSLVT: Chiết khấu Đại lý vùng trắng

        if self.partner_southern_agency:
            discount_product_codes.add("CKSLMN")  # CKSLMN: Chiết khấu Đại lý miền Nam

        # [>] Separate order lines into discount lines and product lines
        discount_lines = self.order_line.filtered(
            lambda sol: sol.product_id.default_code in discount_product_codes
        )
        product_lines = self.order_line.filtered(
            lambda sol: sol.product_id.product_tmpl_id.detailed_type == "product"
        )

        # [>] Unlink discount lines if there are no product lines in the order
        if discount_lines and not product_lines:
            discount_lines.unlink()

    # ==================================
    # ORM / CURD Methods
    # ==================================

    def write(self, vals):
        if "product_uom_qty" in vals and vals["product_uom_qty"]:
            # [>] Update the Sale Order's Bonus Order
            for order in self:
                order._update_programs_and_rewards()
                order._auto_apply_rewards()

        return super(SaleOrder, self).write(vals)

    # ==================================
    # BUSINESS Methods
    # ==================================

    def compute_discount_for_partner(self, bonus):
        default_code = "CKT"
        try:
            bonus_max = self.bonus_max
            if bonus > bonus_max:
                return False
            else:
                if not self.partner_id:
                    _logger.warning("No partner found for this order.")
                    return False
                if bonus > self.partner_id.amount:
                    return bonus
                total_bonus = bonus + self.bonus_order
                if total_bonus > bonus_max:
                    return total_bonus

                # Filter order lines for products
                product_order_lines = self.order_line.filtered(
                    lambda sol: sol.product_id.default_code == default_code
                )
                if not product_order_lines:
                    # Create new product template if it doesn't exist
                    product_discount = self.env["product.template"].search(
                        [("default_code", "=", default_code)]
                    )
                    if not product_discount:
                        product_discount = (
                            self.env["product.template"]
                            .sudo()
                            .create(
                                {
                                    "name": "Chiết khấu tháng",
                                    "detailed_type": "service",
                                    "categ_id": 1,
                                    "taxes_id": False,
                                    "default_code": default_code,
                                }
                            )
                        )

                    # Check for existing discount line
                    discount_order_line = self.order_line.filtered(
                        lambda sol: sol.product_id.default_code == default_code
                    )
                    if not discount_order_line:
                        self.env["sale.order.line"].create(
                            {
                                "order_id": self.id,
                                "product_id": product_discount.product_variant_ids[
                                    0
                                ].id,
                                "code_product": default_code,
                                "product_uom_qty": 1,
                                "price_unit": -total_bonus,
                                "hidden_show_qty": True,
                            }
                        )
                        _logger.info("Created discount line for partner.")
                else:
                    # Update price unit of the order line
                    self.order_line.filtered(
                        lambda sol: sol.product_id.default_code == default_code
                    ).write(
                        {
                            "price_unit": -total_bonus,
                        }
                    )

            # [>] Update the Sale Order's Bonus Order
            self._compute_partner_bonus()
            return True
        except Exception as e:
            _logger.error("Failed to compute discount for partner: %s", e)
            return False

    def action_compute_discount(self):
        if self._is_order_returns() or not self.order_line:
            return

        if self.locked:
            raise UserError("Không thể nhập chiết khấu sản lượng cho đơn hàng đã khóa.")

        self._compute_partner_bonus()
        self._compute_bonus_order_line()

        quantity_change = self._calculate_quantity_change()
        discount_lines, delivery_lines = self._filter_order_lines()
        self._handle_quantity_change(quantity_change, discount_lines, delivery_lines)

        return self._handle_discount_applying()

    def _filter_order_lines(self):
        order = self
        order_lines_discount = order.order_line._filter_discount_agency_lines(order)
        order_lines_delivery = order.order_line.filtered("is_delivery")
        return order_lines_discount, order_lines_delivery

    def action_recompute_discount(self):
        if self._is_order_returns() or not self.order_line:
            return

        if self.locked:
            raise UserError("Không thể nhập chiết khấu sản lượng cho đơn hàng đã khóa.")

        self._compute_partner_bonus()
        self._compute_bonus_order_line()

        quantity_change = self._calculate_quantity_change()
        discount_lines, delivery_lines = self._filter_order_lines()

        self._handle_quantity_change(quantity_change, discount_lines, delivery_lines)

        return self._handle_discount_applying()

    def create_discount_bank_guarantee(self):
        order = self
        default_code = "CKBL"

        # [!] Kiểm tra tồn tại Sản Phẩm dịch vụ cho Chiết Khấu Bảo Lãnh
        product_discount_CKBL = self.env["product.product"].search(
            [("default_code", "=", default_code)], limit=1
        )
        if not product_discount_CKBL:
            self.env["product.product"].sudo().create(
                {
                    "name": "Chiết khấu bảo lãnh",
                    "default_code": "CKBL",
                    "type": "service",
                    "invoice_policy": "order",
                    "list_price": 0.0,
                    "company_id": self.company_id.id,
                    "taxes_id": None,
                }
            )

        # [!] Kiểm tra đã có dòng Chiết Khấu Bảo Lãnh hay chưa?
        discount_order_line = order.order_line.filtered(
            lambda sol: sol.product_id.default_code == default_code
        )
        if discount_order_line:
            # [>] Cập nhật giá sản phẩm
            discount_order_line.write(
                {
                    "price_unit": -order.total_price_after_discount
                    * order.partner_id.discount_bank_guarantee
                    / DISCOUNT_PERCENTAGE_DIVISOR,
                }
            )
        else:
            # [>] Tạo dòng Chiết Khấu Bảo Lãnh
            order.write(
                {
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "order_id": order.id,
                                "product_id": product_discount_CKBL.id,
                                "product_uom_qty": 1,
                                "code_product": default_code,
                                "price_unit": -order.total_price_after_discount
                                * order.partner_id.discount_bank_guarantee
                                / DISCOUNT_PERCENTAGE_DIVISOR,
                                "hidden_show_qty": True,
                            },
                        )
                    ]
                }
            )
            _logger.info("Created discount line for bank guarantee.")

    def _calculate_quantity_change(self):
        return sum(
            line.product_uom_qty
            for line in self.order_line
            if self.check_category_product(line.product_id.categ_id)
            and line.product_id.product_tmpl_id.detailed_type == "product"
        )

    def _handle_quantity_change(self, quantity_change, discount_lines, delivery_lines):
        if self.quantity_change != 0 and self.quantity_change != quantity_change:
            if delivery_lines:
                delivery_lines.unlink()
            if discount_lines:
                discount_lines.unlink()

            self.write({"quantity_change": quantity_change})

    def _handle_discount_applying(self):
        context = dict(self.env.context or {})
        compute_discount_agency = not context.get(
            "action_confirm", False
        ) and context.get("compute_discount_agency")
        recompute_discount_agency = not context.get(
            "action_confirm", False
        ) and context.get("recompute_discount_agency")

        view_id = self.env.ref("mv_sale.mv_wiard_discount_view_form").id
        order_lines_delivery = self.order_line.filtered(lambda sol: sol.is_delivery)
        carrier = (
            (
                self.with_company(
                    self.company_id
                ).partner_shipping_id.property_delivery_carrier_id
                or self.with_company(
                    self.company_id
                ).partner_shipping_id.commercial_partner_id.property_delivery_carrier_id
            )
            if not order_lines_delivery
            else self.carrier_id
        )

        if compute_discount_agency:
            return {
                "name": "Chiết khấu",
                "type": "ir.actions.act_window",
                "res_model": "mv.wizard.discount",
                "view_id": view_id,
                "views": [(view_id, "form")],
                "context": {
                    "default_sale_order_id": self.id,
                    "partner_id": self.partner_id.id,
                    "default_partner_id": self.partner_id.id,
                    "default_discount_amount_apply": self.bonus_remaining,
                    "default_carrier_id": carrier.id,
                    "default_total_weight": self._get_estimated_weight(),
                },
                "target": "new",
            }
        elif recompute_discount_agency:
            return {
                "name": "Cập nhật chiết khấu",
                "type": "ir.actions.act_window",
                "res_model": "mv.wizard.discount",
                "view_id": view_id,
                "views": [(view_id, "form")],
                "context": {
                    "default_sale_order_id": self.id,
                    "partner_id": self.partner_id.id,
                    "default_partner_id": self.partner_id.id,
                    "default_discount_amount_apply": self.bonus_remaining,
                    "default_carrier_id": carrier.id,
                    "default_total_weight": self._get_estimated_weight(),
                },
                "target": "new",
            }

    def _reset_discount_agency(self, order_state=None):
        total_money_to_store_history = self.bonus_order
        is_waiting_approval = (
            total_money_to_store_history > 0 and order_state != "cancel"
        )
        is_positive_money = total_money_to_store_history > 0 and order_state == "cancel"
        if order_state == "cancel":
            description = f"Hủy đơn {self.name}, tiền chiết khấu đã được hoàn về ví."
            money_to_update_history = (
                "+ {:,.2f}".format(total_money_to_store_history)
                if total_money_to_store_history > 0
                else "{:,.2f}".format(total_money_to_store_history)
            )
        elif order_state == "draft":
            description = f"Đơn {self.name} được điều chỉnh về báo giá, tiền chiết khấu đã được hoàn về ví."
            money_to_update_history = (
                "+ {:,.2f}".format(total_money_to_store_history)
                if total_money_to_store_history > 0
                else "{:,.2f}".format(total_money_to_store_history)
            )
        else:
            description = f"Đơn {self.name} đang trong tình trạng xử lý."
            money_to_update_history = "{:,.2f}".format(total_money_to_store_history)

        # Create history line for discount
        if self.partner_id and self.partner_agency:
            self.env["mv.discount.partner.history"]._create_history_line(
                partner_id=self.partner_id.id,
                history_description=description,
                sale_order_id=self.id,
                sale_order_state=self.get_selection_label(self._name, "state", self.id)[
                    1
                ],
                sale_order_discount_money_apply=total_money_to_store_history,
                total_money=total_money_to_store_history,
                total_money_discount_display=money_to_update_history,
                is_waiting_approval=is_waiting_approval,
                is_positive_money=is_positive_money,
                is_negative_money=False,
            )

        # [>] Reset Bonus, Discount Fields
        if order_state == "draft":
            self._compute_partner_bonus()
            self._compute_bonus_order_line()
            self.quantity_change = self._calculate_quantity_change()
        elif order_state == "cancel":
            self.bonus_max = 0
            self.bonus_remaining = 0
            self.bonus_order = 0
            self.quantity_change = 0

            if self.partner_agency:
                self.partner_id.sudo().action_update_discount_amount()

        # [>] Remove Discount Agency Lines
        if order_state in ["draft", "cancel"]:
            self.action_clear_discount_lines()

    def action_clear_discount_lines(self):
        # Filter the order lines based on the conditions
        discount_lines = self.order_line._get_discount_agency_line()
        discount_lines += self.order_line.filtered(lambda sol: sol.is_reward_line)

        # Unlink the discount lines
        if discount_lines:
            discount_lines.sudo().unlink()

    def action_draft(self):
        for order in self:
            order._reset_discount_agency(order_state="draft")

        return super(SaleOrder, self).action_draft()

    def action_cancel(self):
        for order in self:
            order._reset_discount_agency(order_state="cancel")

        return super(SaleOrder, self).action_cancel()

    def action_confirm(self):
        # Filter orders into categories for processing
        orders_return = self.filtered(lambda so: so.is_order_returns)
        orders_agency = self.filtered(
            lambda so: not so.is_order_returns and so.partner_id.is_agency
        )

        # Process return orders
        if orders_return:
            self._process_return_orders(orders_return)
            return super(SaleOrder, orders_return).action_confirm()

        # Process agency orders
        if orders_agency:
            if not all(
                order._can_not_confirmation_without_required_lines()
                for order in orders_agency
            ):
                error_message = (
                    "Các đơn hàng sau không có Phương thức vận chuyển HOẶC Chiết Khấu Sản Lượng, vui lòng kiểm tra: %s"
                    % ", ".join(orders_agency.mapped("display_name")),
                )
                raise UserError(error_message)

            self._process_agency_orders(orders_agency)

            # Create history line for discount
            for order in orders_agency:
                total_money_to_store_history = order.bonus_order
                is_negative_money = total_money_to_store_history > 0
                description = (
                    f"Đã xác nhận đơn {order.name}, tiền chiết khấu đã được khấu trừ."
                )
                money_to_update_history = (
                    "- {:,.2f}".format(total_money_to_store_history)
                    if total_money_to_store_history > 0
                    else "{:,.2f}".format(total_money_to_store_history)
                )
                self.env["mv.discount.partner.history"]._create_history_line(
                    partner_id=order.partner_id.id,
                    history_description=description,
                    sale_order_id=order.id,
                    sale_order_state=self.get_selection_label(
                        order._name, "state", order.id
                    )[1],
                    sale_order_discount_money_apply=total_money_to_store_history,
                    total_money=total_money_to_store_history,
                    total_money_discount_display=money_to_update_history,
                    is_waiting_approval=False,
                    is_positive_money=False,
                    is_negative_money=is_negative_money,
                )
            return super(SaleOrder, orders_agency).action_confirm()

        # Confirm orders not requiring special processing
        orders_regular = self - orders_return - orders_agency
        if orders_regular:
            return super(SaleOrder, orders_regular).action_confirm()

    def _process_return_orders(self, orders_return):
        for order in orders_return:
            order._check_delivery_lines()
            order._check_not_free_qty_in_stock()

    def _process_agency_orders(self, orders_agency):
        for order in orders_agency:
            order._check_delivery_lines()
            order._check_not_free_qty_in_stock()
            order.partner_id.action_update_discount_amount()

            # [>] Applying Discount
            quotation_bonus_order = (
                self.env["sale.order.line"]
                .search(
                    [
                        ("order_id", "=", order.id),
                        ("product_id.default_code", "=", "CKT"),
                    ],
                    limit=1,
                )
                .price_unit
            )
            if not self.env.context.get(
                "apply_confirm"
            ) and order.partner_id.amount_currency < abs(quotation_bonus_order):
                # [>] Xử lý chiết khấu khi có sự thay đổi hoặc đang dùng ở một đơn khác của Đại lý
                quotations_discount_applied = (
                    self.env["sale.order"]
                    .search(
                        [
                            ("id", "!=", order.id),
                            ("state", "in", ["draft", "sent"]),
                            ("partner_id", "=", order.partner_id.id),
                            "|",
                            ("partner_id.is_agency", "=", True),
                            ("partner_agency", "=", True),
                        ]
                    )
                    .filtered(
                        lambda so: so.order_line.filtered(
                            lambda so_line: so_line._filter_discount_agency_lines(so)
                        )
                    )
                )
                quotations_discount_applied._compute_partner_bonus()
                quotations_discount_applied._compute_bonus_order_line()
                order_lines_delivery = order.order_line.filtered(
                    lambda sol: sol.is_delivery
                )
                carrier = (
                    (
                        order.with_company(
                            order.company_id
                        ).partner_shipping_id.property_delivery_carrier_id
                        or order.with_company(
                            order.company_id
                        ).partner_shipping_id.commercial_partner_id.property_delivery_carrier_id
                    )
                    if not order_lines_delivery
                    else order.carrier_id
                )

                return {
                    "name": "Cập nhật chiết khấu",
                    "type": "ir.actions.act_window",
                    "res_model": "mv.wizard.discount",
                    "view_id": self.env.ref("mv_sale.mv_wiard_discount_view_form").id,
                    "views": [
                        (
                            self.env.ref("mv_sale.mv_wiard_discount_view_form").id,
                            "form",
                        )
                    ],
                    "context": {
                        "default_sale_order_id": order.id,
                        "partner_id": order.partner_id.id,
                        "default_partner_id": order.partner_id.id,
                        "default_discount_amount_apply": order.bonus_remaining,
                        "default_carrier_id": carrier.id,
                        "default_total_weight": order._get_estimated_weight(),
                        "default_discount_amount_invalid": True,
                    },
                    "target": "new",
                }
            else:
                order.with_context(action_confirm=True).action_recompute_discount()

    # === MOVEO+ FULL OVERRIDE '_get_program_domain', '_update_programs_and_rewards' ===#

    def _get_program_domain(self):
        """
        Returns the base domain that all programs have to comply to.
        """
        self.ensure_one()
        today = fields.Date.context_today(self)
        program_domain = [
            ("active", "=", True),
            ("sale_ok", "=", True),
            ("company_id", "in", (self.company_id.id, False)),
            "|",
            ("pricelist_ids", "=", False),
            ("pricelist_ids", "in", [self.pricelist_id.id]),
            "|",
            ("date_from", "=", False),
            ("date_from", "<=", today),
            "|",
            ("date_to", "=", False),
            ("date_to", ">=", today),
        ]

        # === ĐẠI LÝ CHÍNH THỨC ===#
        if (
            self.partner_agency
            and not self.partner_white_agency
            and not self.partner_southern_agency
        ):
            program_domain += [("partner_agency_ok", "=", self.partner_agency)]
        # === ĐẠI LÝ VÙNG TRẮNG ===#
        elif (
            self.partner_agency
            and self.partner_white_agency
            and not self.partner_southern_agency
        ):
            program_domain += [
                ("partner_white_agency_ok", "=", self.partner_white_agency)
            ]
        # === ĐẠI LÝ MIỀN NAM ===#
        elif (
            self.partner_agency
            and self.partner_southern_agency
            and not self.partner_white_agency
        ):
            program_domain += [
                ("partner_southern_agency_ok", "=", self.partner_southern_agency)
            ]

        return program_domain

    def _update_programs_and_rewards(self):
        """
        Update the programs and rewards of the order.
        """
        context = dict(self.env.context or {})
        context_compute_discount = (
            context.get("compute_discount_agency")
            or context.get("recompute_discount_agency")
            or context.get("applying_partner_discount")
        )
        if context_compute_discount:
            return super()._update_programs_and_rewards()

    def _program_check_compute_points(self, programs):
        """
        [MO+ FULL OVERRIDE]
        Checks the program validity from the order lines as well as computing the number of points to add.
        Returns a dict containing the error message or the points that will be given with the keys 'points'.
        """
        self.ensure_one()

        # Prepare quantities
        order_lines = self._get_not_rewarded_order_lines()
        products = order_lines.product_id
        products_qties = dict.fromkeys(products, 0)
        for line in order_lines:
            products_qties[line.product_id] += line.product_uom_qty
        # Contains the products that can be applied per rule
        products_per_rule = programs._get_valid_products(products)

        # Prepare amounts
        no_effect_lines = self._get_no_effect_on_threshold_lines()
        base_untaxed_amount = self.amount_untaxed - sum(
            line.price_subtotal for line in no_effect_lines
        )
        base_tax_amount = self.amount_tax - sum(
            line.price_tax for line in no_effect_lines
        )
        amounts_per_program = {
            p: {"untaxed": base_untaxed_amount, "tax": base_tax_amount}
            for p in programs
        }
        for line in self.order_line:
            if not line.reward_id or line.reward_id.reward_type != "discount":
                continue
            for program in programs:
                # Do not consider the program's discount + automatic discount lines for the amount to check.
                if (
                    line.reward_id.program_id.trigger == "auto"
                    or line.reward_id.program_id == program
                ):
                    amounts_per_program[program]["untaxed"] -= line.price_subtotal
                    amounts_per_program[program]["tax"] -= line.price_tax

        result = {}
        for program in programs:
            untaxed_amount = amounts_per_program[program]["untaxed"]
            tax_amount = amounts_per_program[program]["tax"]

            # Used for error messages
            # By default False, but True if no rules and applies_on current -> misconfigured coupons program
            code_matched = (
                not bool(program.rule_ids) and program.applies_on == "current"
            )  # Stays false if all triggers have code and none have been activated
            minimum_amount_matched = code_matched
            product_qty_matched = code_matched
            points = 0
            # Some rules may split their points per unit / money spent
            #  (i.e. gift cards 2x50$ must result in two 50$ codes)
            rule_points = []
            program_result = result.setdefault(program, dict())
            for rule in program.rule_ids:
                if rule.mode == "with_code" and rule not in self.code_enabled_rule_ids:
                    continue
                code_matched = True
                rule_amount = rule._compute_amount(self.currency_id)
                if rule_amount > (
                    rule.minimum_amount_tax_mode == "incl"
                    and (untaxed_amount + tax_amount)
                    or untaxed_amount
                ):
                    continue
                minimum_amount_matched = True
                if not products_per_rule.get(rule):
                    continue
                rule_products = products_per_rule[rule]
                ordered_rule_products_qty = sum(
                    products_qties[product] for product in rule_products
                )
                if (
                    ordered_rule_products_qty < rule.minimum_qty
                    or ordered_rule_products_qty > rule.maximum_qty
                    or not rule_products
                ):
                    continue
                product_qty_matched = True
                if not rule.reward_point_amount:
                    continue
                # Count all points separately if the order is for the future and the split option is enabled
                if (
                    program.applies_on == "future"
                    and rule.reward_point_split
                    and rule.reward_point_mode != "order"
                ):
                    if rule.reward_point_mode == "unit":
                        rule_points.extend(
                            rule.reward_point_amount
                            for _ in range(int(ordered_rule_products_qty))
                        )
                    elif rule.reward_point_mode == "money":
                        for line in self.order_line:
                            if (
                                line.is_reward_line
                                or line.product_id not in rule_products
                                or line.product_uom_qty <= 0
                            ):
                                continue
                            points_per_unit = float_round(
                                (
                                    rule.reward_point_amount
                                    * line.price_total
                                    / line.product_uom_qty
                                ),
                                precision_digits=2,
                                rounding_method="DOWN",
                            )
                            if not points_per_unit:
                                continue
                            rule_points.extend(
                                [points_per_unit] * int(line.product_uom_qty)
                            )
                else:
                    # All checks have been passed we can now compute the points to give
                    if rule.reward_point_mode == "order":
                        points += rule.reward_point_amount
                    elif rule.reward_point_mode == "money":
                        # Compute amount paid for rule
                        # NOTE: this does not account for discounts -> 1 point per $ * (100$ - 30%) will result in 100 points
                        amount_paid = sum(
                            max(0, line.price_total)
                            for line in order_lines
                            if line.product_id in rule_products
                        )
                        points += float_round(
                            rule.reward_point_amount * amount_paid,
                            precision_digits=2,
                            rounding_method="DOWN",
                        )
                    elif rule.reward_point_mode == "unit":
                        points += rule.reward_point_amount * ordered_rule_products_qty
            # NOTE: for programs that are nominative we always allow the program to be 'applied' on the order
            #  with 0 points so that `_get_claimable_rewards` returns the rewards associated with those programs
            if not program.is_nominative:
                if not code_matched:
                    program_result["error"] = _(
                        "This program requires a code to be applied."
                    )
                elif not minimum_amount_matched:
                    program_result["error"] = _(
                        "A minimum of %(amount)s %(currency)s should be purchased to get the reward",
                        amount=min(program.rule_ids.mapped("minimum_amount")),
                        currency=program.currency_id.name,
                    )
                elif not product_qty_matched:
                    program_result["error"] = _(
                        "You don't have the required product quantities on your sales order."
                    )
            elif not self._allow_nominative_programs():
                program_result["error"] = _(
                    "This program is not available for public users."
                )
            if "error" not in program_result:
                points_result = [points] + rule_points
                program_result["points"] = points_result
        return result

    # ==================================
    # CONSTRAINS / VALIDATION Methods
    # ==================================

    def _can_not_confirmation_without_required_lines(self):
        self.ensure_one()

        order = self
        delivery_line = order.delivery_set or order.order_line.filtered(
            lambda sol: sol.is_delivery
        )
        discount_agency_line = self.order_line._filter_discount_agency_lines(order)
        return delivery_line and discount_agency_line

    def _check_delivery_lines(self):
        order = self
        delivery_lines = order.delivery_set or order.order_line.filtered(
            lambda sol: sol.is_delivery
        )
        if not delivery_lines:
            raise UserError("Không tìm thấy dòng giao hàng nào trong đơn hàng.")

    def _check_not_free_qty_in_stock(self):
        if self.state not in ["draft", "sent"]:
            return

        # Use list comprehension instead of filtered method
        product_order_lines = [
            line
            for line in self.order_line
            if line.product_id.product_tmpl_id.detailed_type == "product"
        ]

        error_products = []
        if product_order_lines:
            for so_line in product_order_lines:
                if so_line.product_uom_qty > so_line.free_qty_today:
                    error_products.append(
                        f"\n- {so_line.product_template_id.name}. [ Số lượng có thể đặt: {int(so_line.free_qty_today)} (Cái) ]"
                    )

        # Raise all errors at once
        if error_products:
            error_message = (
                "Bạn không được phép đặt quá số lượng hiện tại:"
                + "".join(error_products)
                + "\n\nVui lòng kiểm tra lại số lượng còn lại trong kho!"
            )
            raise ValidationError(error_message)

    # ==================================
    # TOOLING
    # ==================================

    def get_selection_label(self, model_name, field_name, record_id):
        model = self.env[model_name]
        field = model._fields[field_name]
        selection_values = dict(field.selection)

        record = model.browse(record_id)
        selection_key = getattr(record, field_name)
        selection_label = selection_values.get(selection_key, "Unknown")

        return selection_key, selection_label

    def field_exists(self, model_name, field_name):
        """
        Check if a field exists on the model.

        Args:
            model_name (str): The name of Model to check.
            field_name (str): The name of Field to check.

        Returns:
            bool: True if the field exists, False otherwise.
        """
        # Get the definition of each field on the model
        f = self.env[model_name].fields_get()

        # Check if the field name is in the keys of the fields dictionary
        return field_name in f.keys()

    def _is_order_returns(self):
        return self.is_order_returns

    # =============================================================
    # TRIGGER Methods (Public)
    # These methods are called when a record is updated or deleted.
    # TODO: Update theses functional - Phat Dang <phat.dangminh@moveoplus.com>
    # =============================================================

    def so_trigger_update(self):
        """=== This method is called when a record is updated or deleted ==="""
        try:
            self._compute_partner_bonus()  # Update partner bonus
            self._compute_bonus_order_line()  # Update bonus order line
        except Exception as e:
            _logger.error("Failed to trigger update recordset: %s", e)
            return False
