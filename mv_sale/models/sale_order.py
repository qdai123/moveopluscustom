# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo import http
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

TARGET_CATEGORY_ID = 19
DISCOUNT_PERCENTAGE_DIVISOR = 100
DISCOUNT_QUANTITY_THRESHOLD = 10
QUANTITY_THRESHOLD = 4
PARTNER_MODEL = "res.partner"
WHITE_AGENCY_FIELD = "is_white_agency"

GROUP_SALES_MANAGER = "sales_team.group_sale_manager"


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # === Permission Fields ===#
    is_sales_manager = fields.Boolean(compute="_compute_permissions")
    can_compute_so_discount = fields.Boolean(compute="_compute_permissions")
    can_compute_so_partner_discount = fields.Boolean(compute="_compute_permissions")

    @api.depends(
        "state", "order_line", "order_line.product_uom_qty", "order_line.product_id"
    )
    @api.depends_context("uid")
    def _compute_permissions(self):
        """
        Compute the value of the 'is_sales_manager' field and the 'can_compute_so_discount' field for each record.
        The 'is_sales_manager' field value is True if the current user belongs to the 'Sales Manager' group, False otherwise.
        The 'can_compute_so_discount' field value is True if the user is a sales manager and the order is not a delivery and not a service product, False otherwise.
        """
        is_manager = self.env.user.has_group(GROUP_SALES_MANAGER)
        for record in self:
            # Initialize the flags to False
            record.is_sales_manager = is_manager
            record.can_compute_so_discount = False
            record.can_compute_so_partner_discount = False

            # If there are no order lines, or it is a return order, no need to check further
            # Notes: Should be validate 'order_line' too, if not, it will be error
            if record._is_order_returns():
                continue

            # If the user is a sales manager, they can compute both types of discounts
            if is_manager:
                record.can_compute_so_discount = False if record.flag_delivery else True
                record.can_compute_so_partner_discount = (
                    True if record.flag_delivery else False
                )
                continue

            # If the order is not a delivery and not a service product, the user can compute the discount
            if (
                not record.flag_delivery
                and not record.is_product_service_ckt
                and record.state in ["draft", "sent"]
            ):
                record.can_compute_so_discount = True

            # If the order is a delivery and not a service product, the user can compute the partner discount
            if (
                record.flag_delivery
                and not record.is_product_service_ckt
                and record.state in ["draft", "sent"]
            ):
                record.can_compute_so_partner_discount = True

    # ================================================== #

    def compute_delivery_and_discount_flags(self):
        """
        Compute the value of the 'flag_delivery' and 'is_product_service_ckt' fields for each record.
        The 'flag_delivery' field value is True if there is at least one delivery line in the order, False otherwise.
        The 'is_product_service_ckt' field value is True if there is at least one service product with the code "CKT" in the order, False otherwise.
        """
        for record in self:
            # Initialize the flags to False
            record.flag_delivery = False
            record.is_product_service_ckt = False

            # If there are no order lines, no need to check further
            if not record.order_line:
                continue

            # If there is at least one delivery line in the order, set 'flag_delivery' to True
            if (
                len(record.order_line.filtered(lambda line: line.is_delivery)) > 0
                or record.delivery_set
            ):
                record.flag_delivery = True

            # If there is at least one service product with the code "CKT" in the order, set 'is_product_service_ckt' to True
            if any(
                line.product_id.detailed_type == "service"
                and line.product_id.default_code == "CKT"
                for line in record.order_line
            ):
                record.is_product_service_ckt = True

    flag_delivery = fields.Boolean(
        compute="compute_delivery_and_discount_flags",
        help="""Ghi nhận: Khi có bổ sung "Phương thức giao hàng" trên đơn bán.""",
    )
    is_product_service_ckt = fields.Boolean(
        compute="compute_delivery_and_discount_flags",
        help="""Ghi nhận: Khi có bổ sung "Chiết khấu sản lượng (Tháng/Quý/Năm)" trên đơn bán.""",
    )
    is_order_returns = fields.Boolean(
        default=False, help="Ghi nhận: Là đơn đổi/trả hàng."
    )  # TODO: Needs study cases for SO Returns

    # Ngày hóa đơn xác nhận để làm căn cứ tính discount cho đại lý
    date_invoice = fields.Datetime(readonly=True)
    # Giữ số lượng lại, để khi thay đổi thì xóa dòng delivery, chiết khấu tự động, chiết khấu sản lượng
    quantity_change = fields.Float()

    # === Model: [res.partner] Fields ===#
    partner_agency = fields.Boolean(related="partner_id.is_agency", store=True)
    partner_white_agency = fields.Boolean(
        related="partner_id.is_white_agency", store=True
    )

    # === Model: [mv.compute.discount.line] Fields ===#
    discount_line_id = fields.Many2one("mv.compute.discount.line", readonly=True)

    check_discount_10 = fields.Boolean(
        compute="_compute_discount", store=True, copy=False
    )
    check_discount_agency_white_place = fields.Boolean(
        compute="_compute_discount", store=True, copy=False
    )
    discount_agency_white_place_amount = fields.Float(
        compute="_compute_discount", store=True, copy=False
    )
    bank_guarantee = fields.Boolean(
        related="partner_id.bank_guarantee", store=True, copy=False
    )
    discount_bank_guarantee = fields.Float(
        compute="_compute_discount", store=True, copy=False
    )
    after_discount_bank_guarantee = fields.Float(
        compute="_compute_discount", store=True, copy=False
    )
    # === Bonus, Discount FIELDS ===#
    percentage = fields.Float(
        compute="_compute_discount",
        store=True,
        copy=False,
        help="Phần trăm chiết khấu trên từng sản phẩm.",
    )
    bonus_max = fields.Float(
        compute="_compute_discount",
        store=True,
        copy=False,
        help="Số tiền tối đa mà Đại lý có thể áp dụng để tính chiết khấu.",
    )
    bonus_order = fields.Float(
        copy=False,
        help="""
            - Số tiền chiết khấu đang và đã áp dụng trên đơn bán.
            - Thay đổi khi và chỉ khi có hành động "Nhập Chiết Khấu Sản Lượng"
        """,
    )
    bonus_remaining = fields.Float(
        compute="_compute_discount",
        store=True,
        copy=False,
        help="Số tiền còn lại mà Đại lý có thể áp dụng để tính chiết khấu.",
    )
    # TOTAL Fields:
    total_price_no_service = fields.Float(
        compute="_compute_discount",
        store=True,
        copy=False,
        help="Total price without Product Service, No Discount, No Tax",
    )
    total_price_discount = fields.Float(
        compute="_compute_discount",
        store=True,
        copy=False,
        help="Total price discount without Product Service, No Tax",
    )
    total_price_after_discount = fields.Float(
        compute="_compute_discount",
        store=True,
        copy=False,
        help="Total price after discount without Product Service, No Tax",
    )
    total_price_discount_10 = fields.Float(
        compute="_compute_discount",
        help="Total price discount 1% when [product_uom_qty] >= 10",
        store=True,
        copy=False,
    )
    total_price_after_discount_10 = fields.Float(
        compute="_compute_discount",
        store=True,
        copy=False,
        help="Total price after discount 1% when [product_uom_qty] >= 10",
    )
    total_price_after_discount_month = fields.Float(
        compute="_compute_discount",
        store=True,
        copy=False,
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

    def check_show_warning(self):
        """
        Check if there is at least one product in the order line that belongs to the target category
        and if the sum of the quantities of these products is less than QUANTITY_THRESHOLD.

        Returns:
            bool: True if both conditions are met, False otherwise.
        """
        order_line = self.order_line.filtered(
            lambda x: x.product_id.detailed_type == "product"
            and self.check_category_product(x.product_id.categ_id)
        )
        return (
            len(order_line) >= 1
            and sum(order_line.mapped("product_uom_qty")) < QUANTITY_THRESHOLD
        )

    # hàm này để không tính thuế giao hàng
    # def _get_reward_values_discount(self, reward, coupon, **kwargs):
    #     list = super()._get_reward_values_discount(reward, coupon, **kwargs)
    #     for line in list:
    #         b = {'tax_id': False}
    #         line.update(b)
    #     return list

    # hàm này xử lý số lượng trên thẻ cart, nó đang lấy luôn ca sản phẩm dịch vụ
    def _compute_cart_info(self):
        super(SaleOrder, self)._compute_cart_info()
        for order in self:
            service_lines_qty = sum(
                line.product_uom_qty
                for line in order.website_order_line
                if line.product_id.detailed_type != "product"
                and not line.is_reward_line
            )
            order.cart_quantity -= int(service_lines_qty)

    def _get_order_lines_to_report(self):
        res = super(SaleOrder, self)._get_order_lines_to_report()
        return res.sorted(key=lambda r: r.product_id.detailed_type)

    # ==================================

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

    @api.depends("order_line", "order_line.product_uom_qty", "order_line.product_id")
    def _compute_discount(self):
        for record in self:
            # RESET all discount values
            record.reset_discount_values()

            # [!] Kiểm tra có là Đại Lý hay Đại lý vùng trắng không?
            is_partner_agency = record.partner_id.is_agency
            is_partner_agency_white_place = False
            if self.field_exists(PARTNER_MODEL, WHITE_AGENCY_FIELD):
                is_partner_agency_white_place = record.partner_id.is_white_agency

            if is_partner_agency_white_place:
                record.check_discount_10 = False
                record.check_discount_agency_white_place = True
            # [!] Kiểm tra xem thỏa điều kiện để mua đủ trên 10 lốp xe continental
            elif is_partner_agency and record.order_line:
                record.check_discount_10 = record.check_discount_applicable()

            # [!] Tính tổng tiền giá sản phẩm không bao gồm hàng Dịch Vụ,
            #      tính giá gốc ban đầu, không bao gồm Thuế
            if record.order_line:
                record.calculate_discount_values()

            # [!] Nếu đơn hàng không còn lốp xe nữa thì xóa:
            # - "Chiết Khấu Tháng" (CKT)
            # - "Chiết Khấu Bảo Lãnh" (CKBL)
            # - "Chiết khấu Vùng Trắng" (CKSLVT) (Nếu có tồn tại)
            record.handle_discount_lines()

    def reset_discount_values(self):
        self.percentage = 0
        self.check_discount_10 = False
        self.after_discount_bank_guarantee = 0
        self.discount_bank_guarantee = 0
        self.discount_agency_white_place_amount = 0
        self.total_price_no_service = 0
        self.total_price_discount = 0
        self.total_price_after_discount = 0
        self.total_price_discount_10 = 0
        self.total_price_after_discount_10 = 0
        self.total_price_after_discount_month = 0
        self.bonus_max = 0
        self.bonus_remaining = self.partner_id.amount_currency - self.bonus_order

    def check_discount_applicable(self):
        order_line = self.order_line.filtered(
            lambda sol: sol.product_id.detailed_type == "product"
            and self.check_category_product(sol.product_id.categ_id)
        )
        return (
            len(order_line) >= 1
            and sum(order_line.mapped("product_uom_qty")) >= DISCOUNT_QUANTITY_THRESHOLD
        )

    def calculate_discount_values(self):
        total_price_no_service = 0
        total_price_discount = 0
        percentage = 0

        for line in self.order_line.filtered(
            lambda sol: sol.product_id.detailed_type == "product"
        ):
            total_price_no_service += line.price_unit * line.product_uom_qty
            total_price_discount += (
                line.price_unit
                * line.product_uom_qty
                * line.discount
                / DISCOUNT_PERCENTAGE_DIVISOR
            )
            percentage = line.discount
        self.total_price_no_service = total_price_no_service
        self.total_price_discount = total_price_discount
        self.percentage = percentage
        self.total_price_after_discount = (
            self.total_price_no_service - self.total_price_discount
        )

        # [!] Tính chiết khấu bảo lãnh ngân hàng
        if self.partner_id.bank_guarantee:
            self.discount_bank_guarantee = (
                self.total_price_after_discount
                * self.partner_id.discount_bank_guarantee
                / DISCOUNT_PERCENTAGE_DIVISOR
            )
            if self and self.discount_bank_guarantee > 0:
                self.create_discount_bank_guarantee()
        self.after_discount_bank_guarantee = (
            self.total_price_after_discount - self.discount_bank_guarantee
        )
        self.total_price_discount_10 = (
            self.total_price_after_discount / DISCOUNT_PERCENTAGE_DIVISOR
        )
        self.total_price_after_discount_10 = (
            self.after_discount_bank_guarantee - self.total_price_discount_10
        )
        self.total_price_after_discount_month = (
            self.total_price_after_discount_10 - self.bonus_order
        )

        # [!] Tính chiết khấu Đại lý vùng trắng
        if self and self.check_discount_agency_white_place:
            # Filter order lines for products
            product_order_lines = self.order_line.filtered(
                lambda sol: sol.product_id.detailed_type == "product"
                and self.check_category_product(sol.product_id.categ_id)
            )
            # Get partner discount
            partner_discount = self.env["mv.white.place.discount.line"].search(
                [("parent_id", "=", self.partner_id.discount_id.id)],
                limit=1,
            )
            discount_quantity_required = partner_discount.quantity
            discount_for_white_place = partner_discount.discount
            if (
                sum(product_order_lines.mapped("product_uom_qty"))
                >= discount_quantity_required
            ):
                self.discount_agency_white_place_amount = (
                    self.total_price_after_discount * discount_for_white_place / 100
                )

        self.bonus_max = (
            self.total_price_no_service
            - self.total_price_discount
            - self.total_price_discount_10
            - self.discount_bank_guarantee
            - self.discount_agency_white_place_amount
        ) / 2

    def handle_discount_lines(self):
        """
        Removes discount lines from the order if there are no more products in the order.
        Specifically, it checks for the existence of order lines with provided product codes
        and removes them if there are no more products in the order.
        """
        discount_product_codes = {"CKT", "CKBL"}
        if self.check_discount_agency_white_place:
            discount_product_codes.add("CKSLVT")  # CKSLVT: Chiết khấu Đại lý vùng trắng

        # [>] Separate order lines into discount lines and product lines
        discount_lines = self.order_line.filtered(
            lambda sol: sol.product_id.default_code in discount_product_codes
        )
        product_lines = self.order_line.filtered(
            lambda sol: sol.product_id.detailed_type == "product"
        )

        # [>] Unlink discount lines if there are no product lines in the order
        if discount_lines and not product_lines:
            discount_lines.unlink()

    # ==================================
    # ORM / CURD Methods
    # ==================================

    def write(self, vals):
        if self.env.context.get(
            "apply_partner_discount", False
        ) and self.env.user.has_group(GROUP_SALES_MANAGER):
            if "order_line" in vals and vals["order_line"]:
                for record in self:
                    record.compute_discount_for_partner(record.bonus_order)
        return super(SaleOrder, self).write(vals)

    def copy(self, default=None):
        # MOVEOPLUS Override
        orders = super(SaleOrder, self).copy(default)
        orders._update_programs_and_rewards()
        orders._auto_apply_rewards()
        return orders

    # ==================================
    # BUSINESS Methods
    # ==================================

    def compute_discount_for_partner(self, bonus):
        PRODUCT_DISCOUNT_CODE = "CKT"
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
                    lambda sol: sol.product_id.default_code == PRODUCT_DISCOUNT_CODE
                )
                if not product_order_lines:
                    # Create new product template if it doesn't exist
                    product_discount = self.env["product.template"].search(
                        [("default_code", "=", PRODUCT_DISCOUNT_CODE)]
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
                                    "default_code": PRODUCT_DISCOUNT_CODE,
                                }
                            )
                        )

                    # Check for existing discount line
                    discount_order_line = self.order_line.filtered(
                        lambda sol: sol.product_id.default_code == PRODUCT_DISCOUNT_CODE
                    )
                    if not discount_order_line:
                        self.env["sale.order.line"].create(
                            {
                                "order_id": self.id,
                                "product_id": product_discount.product_variant_ids[
                                    0
                                ].id,
                                "code_product": PRODUCT_DISCOUNT_CODE,
                                "product_uom_qty": 1,
                                "price_unit": -total_bonus,
                                "hidden_show_qty": True,
                            }
                        )
                        _logger.info("Created discount line for partner.")
                else:
                    # Update price unit of the order line
                    self.order_line.filtered(
                        lambda sol: sol.product_id.default_code == PRODUCT_DISCOUNT_CODE
                    ).write(
                        {
                            "price_unit": -total_bonus,
                        }
                    )

            # [>] Update the Sale Order's Bonus Order
            self.write(
                {
                    "bonus_order": total_bonus,
                    "bonus_remaining": self.partner_id.amount_currency - total_bonus,
                }
            )
            # [>] Re-compute discount
            self.calculate_discount_values()

            # [>] Update the Partner's Amount
            self.sudo().with_context(trigger_update=True).env["res.partner"].browse(
                self.partner_id.id
            ).write(
                {
                    "amount": self.bonus_remaining,
                    "amount_currency": self.bonus_remaining,
                }
            )
        except Exception as e:
            _logger.error("Failed to compute discount for partner: %s", e)
            return False

    def action_compute_discount_month(self):
        if self._is_order_returns():
            return

        if self.locked:
            raise UserError("Không thể nhập chiết khấu sản lượng cho đơn hàng đã khóa.")

        if not self.check_discount_agency_white_place:
            self._update_programs_and_rewards()
            self._auto_apply_rewards()

        # [!] Thêm chiết khấu cho Đại lý vùng trắng
        self._handle_agency_white_place_discount()

        # [!] Thêm chiết khấu bảo lãnh ngân hàng
        self._handle_bank_guarantee_discount()

        quantity_change = self._calculate_quantity_change()

        discount_order_lines, delivery_order_lines = self._filter_order_lines()

        if not delivery_order_lines:
            return self.action_open_delivery_wizard()

        self._handle_quantity_change(
            quantity_change, discount_order_lines, delivery_order_lines
        )

        return self._handle_discount_confirmation()

    def create_discount_bank_guarantee(self, url=None):
        PRODUCT_DISCOUNT_CODE = "CKBL"
        try:
            if not url:
                url = http.request.httprequest.full_path or ""

            # Check if there are product order lines
            product_order_lines = self.order_line.filtered(
                lambda sol: sol.product_id.detailed_type == "product"
                and self.check_category_product(sol.product_id.categ_id)
            )

            if product_order_lines:
                # Check for existing discount line
                discount_order_line = self.order_line.filtered(
                    lambda sol: sol.product_id.product_tmpl_id.default_code
                    or sol.code_product == PRODUCT_DISCOUNT_CODE
                )

                if not discount_order_line:
                    # Create new product template if it doesn't exist
                    product_discount = self.env["product.template"].search(
                        [("default_code", "=", PRODUCT_DISCOUNT_CODE)]
                    )

                    if not product_discount:
                        product_discount = (
                            self.env["product.template"]
                            .sudo()
                            .create(
                                {
                                    "name": "Chiết khấu bảo lãnh",
                                    "detailed_type": "service",
                                    "categ_id": 1,
                                    "taxes_id": False,
                                    "default_code": PRODUCT_DISCOUNT_CODE,
                                }
                            )
                        )

                    # ===========================================
                    if (
                        url
                        and url.find("/shop/cart") > -1
                        or self._context.get("bank_guarantee", False)
                    ):
                        discount_order_line = self.env["sale.order.line"].create(
                            {
                                "order_id": self.id,
                                "product_id": product_discount.product_variant_ids[
                                    0
                                ].id,
                                "code_product": PRODUCT_DISCOUNT_CODE,
                                "product_uom_qty": 1,
                                "price_unit": 0,
                                "hidden_show_qty": True,
                            }
                        )
                        _logger.info("Created discount line for bank guarantee.")
                    # ===========================================

                # Update price unit of the order line
                if discount_order_line:
                    discount_order_line.write(
                        {
                            "price_unit": -self.total_price_after_discount
                            * self.partner_id.discount_bank_guarantee
                            / DISCOUNT_PERCENTAGE_DIVISOR,
                        }
                    )
        except Exception as e:
            _logger.error("Failed to create discount for bank guarantee: %s", e)

    def _handle_bank_guarantee_discount(self):
        if self.partner_id.bank_guarantee:
            self.discount_bank_guarantee = (
                self.total_price_after_discount
                * self.partner_id.discount_bank_guarantee
                / DISCOUNT_PERCENTAGE_DIVISOR
            )
            if self.discount_bank_guarantee > 0:
                self.with_context(bank_guarantee=True).create_discount_bank_guarantee()

    def create_discount_agency_white_place(self):
        """
        Create a discount for agencies in white places.
        If there is a product in the order line, create a discount line for the agency in white places.
        """
        PRODUCT_DISCOUNT_CODE = "CKSLVT"
        try:
            # Filter order lines for products
            product_order_lines = self.order_line.filtered(
                lambda sol: sol.product_id.detailed_type == "product"
                and self.check_category_product(sol.product_id.categ_id)
            )

            if product_order_lines:
                # Get partner discount
                partner_discount = self.env["mv.white.place.discount.line"].search(
                    [("parent_id", "=", self.partner_id.discount_id.id)],
                    limit=1,
                )
                discount_quantity_required = partner_discount.quantity or 8
                discount_for_white_place = partner_discount.discount or 1.5
                product_discount_name = f"Chiết khấu giao hàng (SL tối thiểu {discount_quantity_required} lốp) ({discount_for_white_place}%)"

                # Check for existing discount line
                discount_order_line = self.order_line.filtered(
                    lambda sol: sol.product_id.product_tmpl_id.default_code
                    == PRODUCT_DISCOUNT_CODE
                    or sol.code_product == PRODUCT_DISCOUNT_CODE
                )

                if not discount_order_line:
                    # Create new product template if it doesn't exist
                    product_discount = self.env["product.template"].search(
                        [("default_code", "=", PRODUCT_DISCOUNT_CODE)]
                    )
                    if not product_discount:
                        product_discount = (
                            self.env["product.template"]
                            .sudo()
                            .create(
                                {
                                    "name": product_discount_name,
                                    "detailed_type": "service",
                                    "categ_id": 1,
                                    "taxes_id": False,
                                    "default_code": PRODUCT_DISCOUNT_CODE,
                                    "purchase_ok": False,
                                }
                            )
                        )
                    else:
                        product_discount.sudo().write({"name": product_discount_name})

                    # ===========================================
                    current_url = http.request.httprequest.full_path
                    if (
                        current_url
                        and current_url.find("/shop/cart") > -1
                        or self._context.get(
                            "compute_discount_for_agency_white_place", False
                        )
                    ):
                        discount_order_line = self.env["sale.order.line"].create(
                            {
                                "order_id": self.id,
                                "product_id": product_discount.product_variant_ids[
                                    0
                                ].id,
                                "code_product": PRODUCT_DISCOUNT_CODE,
                                "product_uom_qty": 1,
                                "price_unit": 0,
                                "hidden_show_qty": True,
                            }
                        )
                        _logger.info("Created discount line for agency in white place.")
                    # ===========================================

                # Update price unit of the order line
                if (
                    sum(product_order_lines.mapped("product_uom_qty"))
                    >= discount_quantity_required
                ):
                    discount_order_line.write(
                        {
                            "price_unit": -self.total_price_after_discount
                            * discount_for_white_place
                            / 100,
                        }
                    )
        except Exception as e:
            _logger.error("Failed to create discount for agency in white place: %s", e)

    def _handle_agency_white_place_discount(self):
        if self.check_discount_agency_white_place:
            # Get partner discount
            partner_discount = self.env["mv.white.place.discount.line"].search(
                [("parent_id", "=", self.partner_id.discount_id.id)],
                limit=1,
            )
            discount_quantity_required = partner_discount.quantity or 8

            # Filter order lines for products
            product_related_order_lines = self.order_line.filtered(
                lambda sol: sol.product_id.detailed_type == "product"
                and self.check_category_product(sol.product_id.categ_id)
            )

            # Check if the total quantity of product related order lines is greater than or equal to the required discount quantity
            total_quantity = sum(product_related_order_lines.mapped("product_uom_qty"))
            is_discount_applicable = total_quantity >= discount_quantity_required

            if is_discount_applicable:
                self.with_context(
                    compute_discount_for_agency_white_place=True
                ).create_discount_agency_white_place()

    def _calculate_quantity_change(self):
        return sum(
            line.product_uom_qty
            for line in self.order_line
            if line.product_id.detailed_type == "product"
            and self.check_category_product(line.product_id.categ_id)
        )

    def _handle_quantity_change(
        self, quantity_change, discount_order_lines, delivery_order_lines
    ):
        if self.quantity_change != 0 and self.quantity_change != quantity_change:
            if delivery_order_lines:
                delivery_order_lines.unlink()
            if discount_order_lines:
                discount_order_lines.unlink()

        self.write({"quantity_change": quantity_change})

    def _filter_order_lines(self):
        discount_order_lines = self.order_line.filtered(
            lambda sol: sol.product_id.default_code == "CKT"
        )
        delivery_order_lines = self.order_line.filtered(lambda sol: sol.is_delivery)
        return discount_order_lines, delivery_order_lines

    def _handle_discount_confirmation(self):
        if not self._context.get("confirm", False):
            view_id = self.env.ref("mv_sale.mv_wiard_discount_view_form").id
            if self.env.context.get("apply_partner_discount_amount"):
                name = "Nhập chiết khấu sản lượng (Tháng/Quý/Năm)"
            else:
                name = "Nhập phương thức giao hàng"
            return {
                "name": name,
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "mv.wizard.discount",
                "view_id": view_id,
                "views": [(view_id, "form")],
                "target": "new",
                "context": {
                    "default_order_id": self.id,
                    "default_amount": self.bonus_remaining,
                    "default_bonus_remaining": self.bonus_remaining,
                },
            }

    def action_draft(self):
        if self.bonus_order > 0:
            if self.partner_id:
                _logger.info("Adding bonus order amount back to partner's amount.")
                self.partner_id.write(
                    {"amount": self.partner_id.amount + self.bonus_order}
                )
            else:
                _logger.warning("No partner found for this order.")
            self.write({"bonus_order": 0})
        return super(SaleOrder, self).action_draft()

    def action_confirm(self):
        self._check_delivery_lines()
        self._check_order_not_free_qty_today()
        self._handle_agency_discount()
        return super(SaleOrder, self).action_confirm()

    def action_cancel(self):
        if self.bonus_order > 0:
            if self.partner_id:
                _logger.info("Adding bonus order amount back to partner's amount.")
                self.partner_id.write(
                    {"amount": self.partner_id.amount + self.bonus_order}
                )
            else:
                _logger.warning("No partner found for this order.")
            self.write({"bonus_order": 0, "quantity_change": 0})
        return super(SaleOrder, self).action_cancel()

    # ==================================
    # CONSTRAINS / VALIDATION Methods
    # ==================================

    def _check_delivery_lines(self):
        delivery_lines = self.order_line.filtered(lambda sol: sol.is_delivery)
        if not delivery_lines:
            raise UserError("Không tìm thấy dòng giao hàng nào trong đơn hàng.")

    def _check_order_not_free_qty_today(self):
        for so in self:
            if so.state not in ["draft", "sent"]:
                continue

            # Use list comprehension instead of filtered method
            product_order_lines = [
                line
                for line in so.order_line
                if line.product_id.detailed_type == "product"
            ]

            if product_order_lines:
                error_products = []
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

    def _handle_agency_discount(self):
        # Filter out orders that are returns
        non_return_orders = self.filtered(lambda order: not order.is_order_returns)

        # Filter out orders that are not by partner agency
        agency_orders = non_return_orders.filtered(
            lambda order: order.partner_id.is_agency
        )

        # Compute discount for agency orders
        agency_orders.with_context(confirm=True).action_compute_discount_month()

    # =============================================================
    # TRIGGER Methods (Public)
    # These methods are called when a record is updated or deleted.
    # =============================================================

    def trigger_update(self):
        """=== This method is called when a record is updated or deleted ==="""
        if self._context.get("trigger_update", False):
            try:
                # Update the discount amount in the sale order
                self._update_sale_order_discount_amount()

                # Update the partner's discount amount
                self._update_partner_discount_amount()
            except Exception as e:
                # Log any exceptions that occur
                _logger.error("Failed to trigger update recordset: %s", e)

    def _update_sale_order_discount_amount(self):
        for order in self:
            print(f"Write your logic code here. {order.name_get()}")

        return True

    def _update_partner_discount_amount(self):
        for order in self.filtered(
            lambda so: so.partner_id.is_agency and so.bonus_order > 0
        ):
            try:
                # Calculate the total bonus
                total_bonus = order.partner_id.amount_currency - order.bonus_order

                # Update the partner's discount amount
                order.partner_id.write(
                    {"amount": total_bonus, "amount_currency": total_bonus}
                )
            except Exception as e:
                # Log any exceptions that occur
                _logger.error("Failed to update partner discount amount: %s", e)

        return True

    # ==================================
    # TOOLING
    # ==================================

    def _is_order_returns(self):
        self.ensure_one()
        return self.is_order_returns
