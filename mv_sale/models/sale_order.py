# -*- coding: utf-8 -*-
import logging

from odoo import http
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

TARGET_CATEGORY_ID = 19
DISCOUNT_PERCENTAGE_DIVISOR = 100
DISCOUNT_QUANTITY_THRESHOLD = 10
QUANTITY_THRESHOLD = 4
PARTNER_MODEL = "res.partner"
WHITE_AGENCY_FIELD = "is_white_agency"


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ACCESS/RULE Fields:
    is_sales_manager = fields.Boolean(
        compute="_compute_is_sales_manager",
        default=lambda self: self.env.user.has_group("sales_team.group_sale_manager"),
    )

    @api.depends_context("uid")
    def _compute_is_sales_manager(self):
        """
        Compute the value of the 'is_sales_manager' field for each record.
        The field value is True if the current user belongs to the 'Sales Manager' group, False otherwise.
        """
        is_manager = self.env.user.has_group("sales_team.group_sale_manager")
        for record in self:
            record.is_sales_manager = is_manager

    discount_line_id = fields.Many2one(
        "mv.compute.discount.line"
    )  # Make sure this field is not useless

    # Ngày hóa đơn xác nhận để làm căn cứ tính discount cho đại lý
    date_invoice = fields.Datetime("Date invoice", readonly=True)
    # Giữ số lượng lại, để khi thay đổi thì xóa dòng delivery, chiết khấu tự động, chiết khấu sản lượng
    quantity_change = fields.Float(copy=False)
    flag_delivery = fields.Boolean(compute="compute_flag_delivery")

    # [res.partner] Fields:
    partner_agency = fields.Boolean(related="partner_id.is_agency", store=True)
    partner_white_agency = fields.Boolean(
        related="partner_id.is_white_agency", store=True
    )

    def compute_flag_delivery(self):
        for record in self:
            record.flag_delivery = False
            if (
                len(record.order_line) > 0
                and len(self.order_line.filtered(lambda x: x.is_delivery)) > 0
            ):
                record.flag_delivery = True

    # DISCOUNT for Partner Agency with (SL >= 10) (1%) - CKSL
    check_discount_10 = fields.Boolean(
        compute="_compute_discount", store=True, copy=False
    )
    # DISCOUNT for Partner Agency White Place with (SL >= 8) (1.5%) - CKSLVT
    check_discount_agency_white_place = fields.Boolean(
        compute="_compute_discount", store=True, copy=False
    )
    discount_agency_white_place_amount = fields.Float(
        "Số tiền Chiết khấu Vùng Trắng",
        compute="_compute_discount",
        store=True,
        copy=False,
    )
    # DISCOUNT for Partner Agency has Bank Guarantee (0.5%) - CKBL
    bank_guarantee = fields.Boolean(
        "Bảo lãnh ngân hàng", related="partner_id.bank_guarantee", store=True
    )
    discount_bank_guarantee = fields.Float(
        "Số tiền Bảo lãnh Ngân Hàng",
        compute="_compute_discount",
        store=True,
        copy=False,
    )
    after_discount_bank_guarantee = fields.Float(
        compute="_compute_discount",
        help="Total price after Discount Bank Guarantee",
        store=True,
        copy=False,
    )
    # % Discount Fields:
    percentage = fields.Float(
        compute="_compute_discount",
        help="% Discount of Pricelist",
        store=True,
        copy=False,
    )
    # TOTAL Fields:
    total_price_no_service = fields.Float(
        compute="_compute_discount",
        help="Total price without Product Service, No Discount, No Tax",
        store=True,
        copy=False,
    )
    total_price_discount = fields.Float(
        compute="_compute_discount",
        help="Total price discount without Product Service, No Tax",
        store=True,
        copy=False,
    )
    total_price_after_discount = fields.Float(
        compute="_compute_discount",
        help="Total price after discount without Product Service, No Tax",
        store=True,
        copy=False,
    )
    total_price_discount_10 = fields.Float(
        compute="_compute_discount",
        help="Total price discount 1% when [product_uom_qty] >= 10",
        store=True,
        copy=False,
    )
    total_price_after_discount_10 = fields.Float(
        compute="_compute_discount",
        help="Total price after discount 1% when [product_uom_qty] >= 10",
        store=True,
        copy=False,
    )
    # tổng số tiền tối đa mà khách hàng có thể áp dụng chiết khấu từ tài khoản bonus của mình
    bonus_max = fields.Float(
        compute="_compute_discount",
        help="Total price after discount 1% when [product_uom_qty] >= 10",
        store=True,
        copy=False,
    )
    # tổng số tiền mà khách hàng đã áp dụng giảm chiết khấu
    bonus_order = fields.Float(copy=False)
    total_price_after_discount_month = fields.Float(
        compute="_compute_discount",
        help="Total price after discount for a month",
        store=True,
        copy=False,
    )

    # thuật toán kiếm cha là lốp xe
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
            service_lines = order.website_order_line.filtered(
                lambda line: line.product_id.detailed_type != "product"
                and not line.is_reward_line
            )
            order.cart_quantity -= int(sum(service_lines.mapped("product_uom_qty")))

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

            # [!] Tính tổng tiền giá sản phẩm không bao gồm hàng dịch vụ,
            #      tính giá gốc ban đầu, không bao gồm thuế phí
            if record.order_line:
                record.calculate_discount_values()

            # [!] Nếu đơn hàng không còn lốp xe nữa thì xóa:
            # - "Chiết Khấu Tháng" (CKT)
            # - "Chiết Khấu Bảo Lãnh" (CKBL)
            # - "Chiết khấu Vùng Trắng" (CKSLVT) (IF EXISTS)
            record.handle_discount_lines()

    def reset_discount_values(self):
        self.check_discount_10 = False
        self.total_price_no_service = 0
        self.total_price_discount = 0
        self.percentage = 0
        self.total_price_after_discount = 0
        self.total_price_discount_10 = 0
        self.total_price_after_discount_10 = 0
        self.after_discount_bank_guarantee = 0
        self.discount_bank_guarantee = 0
        self.discount_agency_white_place_amount = 0
        self.total_price_after_discount_month = 0
        self.bonus_max = 0

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
            discount_quantity_required = partner_discount.quantity or 8
            discount_for_white_place = partner_discount.discount or 1.5
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
        Specifically, it checks for the existence of order lines with product codes "CKT", "CKBL" and "CKSLVT"
        and removes them if there are no more products in the order.
        """
        product_ref = ["CKT", "CKBL"]
        if self.check_discount_agency_white_place:
            product_ref.append("CKSLVT")  # CKSLVT: Chiết khấu Đại lý vùng trắng

        order_line_ctk = self.order_line.filtered(
            lambda sol: sol.product_id.default_code in product_ref
        )
        order_line_product = self.order_line.filtered(
            lambda sol: sol.product_id.detailed_type == "product"
        )

        if order_line_ctk and not order_line_product:
            order_line_ctk.unlink()

    # ==================================
    # ORM Methods
    # ==================================

    def copy(self, default=None):
        # MOVEOPLUS Override
        res = super(SaleOrder, self).copy(default)
        res._update_programs_and_rewards()
        res._auto_apply_rewards()
        return res

    # ==================================
    # BUSINESS Methods
    # ==================================

    def compute_discount_for_partner(self, bonus):
        """
        Compute the discount for a partner based on the bonus.
        If the bonus is greater than the maximum bonus, return False.
        Otherwise, check if the bonus is greater than the partner's amount.
        If it is, return the bonus.
        Then calculate the total bonus and check if it is greater than the maximum bonus.
        If it is, return the total bonus.
        Then check if there is an order line with the product code "CKT".
        If there isn't, create a new product template with the code "CKT" and create a new order line with this product.
        Then update the price unit of the order line and the bonus order of the sale order and decrease the amount of the partner.
        """
        PRODUCT_DISCOUNT_CODE = "CKT"
        try:
            if bonus > self.bonus_max:
                return False
            else:
                if not self.partner_id:
                    _logger.warning("No partner found for this order.")
                    return False
                if bonus > self.partner_id.amount:
                    return bonus
                total_bonus = bonus + self.bonus_order
                if total_bonus > self.bonus_max:
                    return total_bonus

                # Filter order lines for products
                product_order_lines = self.order_line.filtered(
                    lambda sol: sol.product_id.default_code == PRODUCT_DISCOUNT_CODE
                )

                if not product_order_lines:
                    # Check for existing discount line
                    discount_order_line = self.order_line.filtered(
                        lambda sol: sol.product_id.default_code == PRODUCT_DISCOUNT_CODE
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
                                        "name": "Chiết khấu tháng",
                                        "detailed_type": "service",
                                        "categ_id": 1,
                                        "taxes_id": False,
                                        "default_code": PRODUCT_DISCOUNT_CODE,
                                    }
                                )
                            )

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
                        _logger.info("Created discount line for partner.")

                    # Update price unit of the order line
                    if discount_order_line:
                        discount_order_line.write(
                            {
                                "price_unit": -total_bonus,
                            }
                        )

            self.write({"bonus_order": total_bonus})
            self.partner_id.write({"amount": self.partner_id.amount - bonus})
        except Exception as e:
            _logger.error("Failed to compute discount for partner: %s", e)

    def action_compute_discount_month(self):
        if not self.order_line:
            return

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

    def _filter_order_lines(self):
        discount_order_lines = self.order_line.filtered(
            lambda sol: sol.product_id.default_code == "CKT"
        )
        delivery_order_lines = self.order_line.filtered(lambda sol: sol.is_delivery)
        return discount_order_lines, delivery_order_lines

    def _handle_quantity_change(
        self, quantity_change, discount_order_lines, delivery_order_lines
    ):
        if self.quantity_change != 0 and self.quantity_change != quantity_change:
            if delivery_order_lines:
                delivery_order_lines.unlink()
            if discount_order_lines:
                discount_order_lines.unlink()

        self.write({"quantity_change": quantity_change})

    def _handle_discount_confirmation(self):
        if not self._context.get("confirm", False):
            view_id = self.env.ref("mv_sale.mv_wiard_discount_view_form").id
            return {
                "name": "Chiết khấu",
                "type": "ir.actions.act_window",
                "view_mode": "form",
                "res_model": "mv.wizard.discount",
                "view_id": view_id,
                "views": [(view_id, "form")],
                "target": "new",
                "context": {
                    "default_sale_id": self.id,
                    "default_partner_id": self.partner_id.id,
                    "default_currency_id": self.currency_id.id
                    or self.env.company.currency_id.id,
                },
            }

    def action_draft(self):
        """
        Handle the transition of a sale order back to the draft state.
        If there is a bonus order, add the bonus order amount back to the partner's amount.
        Reset the bonus order to 0.
        Then call the parent class's action_draft method.
        """
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
        """
        Confirm the sale order.
        It checks if the quantity of the product in the order line is greater than the available quantity for the day.
        If it is, it raises a validation error.
        If the partner is an agency, it computes the discount for the month.
        If there are no delivery lines in the order, it raises a user error.
        Then it confirms the sale order and logs any exceptions that occur during this process.
        """
        self._check_order_not_free_qty()
        self._handle_agency_discount()
        self._check_delivery_lines()
        return super(SaleOrder, self).action_confirm()

    def action_cancel(self):
        """
        Handle the cancellation of a sale order.
        If there is a bonus order, add the bonus order amount back to the partner's amount.
        Reset the bonus order and quantity change to 0.
        Then call the parent class's action_cancel method.
        """
        if self.bonus_order > 0:
            if self.partner_id:
                _logger.info("Adding bonus order amount back to partner's amount.")
                self.partner_id.write(
                    {"amount": self.partner_id.amount + self.bonus_order}
                )
            else:
                _logger.warning("No partner found for this order.")
            self.write(
                {
                    "bonus_order": 0,
                    "quantity_change": 0,
                }
            )
        return super(SaleOrder, self).action_cancel()

    # ==================================
    # CONSTRAINS / VALIDATION Methods
    # ==================================

    def _check_order_not_free_qty(self):
        """
        Check if the quantity of the product in the order line is greater than the available quantity for the day.
        If it is, raise a validation error.
        """
        for so in self.filtered(lambda rec: rec.state in ["draft", "sent"]):
            product_order_lines = so.order_line.filtered(
                lambda sol: sol.product_id.detailed_type == "product"
            )
            if product_order_lines:
                for so_line in product_order_lines:
                    if so_line.product_uom_qty > so_line.free_qty_today:
                        error_message = (
                            f"Bạn không được phép đặt quá số lượng hiện tại:"
                            f"\n- Sản phẩm: {so_line.product_template_id.name}"
                            f"\n- Số lượng hiện tại có thể đặt: {int(so_line.free_qty_today)} Cái"
                            f"\n\nVui lòng kiểm tra lại số lượng còn lại trong kho."
                        )
                        raise ValidationError(error_message)

        return False

    def _handle_agency_discount(self):
        """
        Handle the discount for the agency.
        """
        if self.partner_id.is_agency:
            self.with_context(confirm=True).action_compute_discount_month()

    def _check_delivery_lines(self):
        """
        Check if there are delivery lines in the order.
        If there are no delivery lines, raise a user error.
        """
        delivery_lines = self.order_line.filtered(lambda sol: sol.is_delivery)
        if not delivery_lines:
            raise UserError(_("No delivery lines were found in the order."))
