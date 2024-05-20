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


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ACCESS/RULE Fields:
    is_sales_manager = fields.Boolean(
        compute="_compute_is_sales_manager",
        default=lambda self: self.env.user.has_group("sales_team.group_sale_manager"),
    )

    @api.depends_context("uid")
    def _compute_is_sales_manager(self):
        is_manager = self.env.user.has_group("sales_team.group_sale_manager")

        for user in self:
            user.is_sales_manager = is_manager

    discount_line_id = fields.Many2one(
        "mv.compute.discount.line"
    )  # Make sure this field is not useless

    # Ngày hóa đơn xác nhận để làm căn cứ tính discount cho đại lý
    date_invoice = fields.Datetime("Date invoice", readonly=True)
    # Giữ số lượng lại, để khi thay đổi thì xóa dòng delivery, chiết khấu tự động, chiết khấu sản lượng
    quantity_change = fields.Float(copy=False)
    flag_delivery = fields.Boolean(compute="compute_flag_delivery")

    def compute_flag_delivery(self):
        for record in self:
            record.flag_delivery = False
            if (
                len(record.order_line) > 0
                and len(self.order_line.filtered(lambda x: x.is_delivery)) > 0
            ):
                record.flag_delivery = True

    # DISCOUNT for Partner Agency with (SL >= 10) (1%) - CKSLL
    check_discount_10 = fields.Boolean(
        compute="_compute_discount", store=True, copy=False
    )
    # DISCOUNT for Partner Agency White Place with (SL >= 8) (1.5%) - CKSLVT
    check_discount_agency_white_place = fields.Boolean(
        compute="_compute_discount", store=True, copy=False
    )
    # DISCOUNT for Partner Agency has Bank Guarantee (0.5%) - CKBL
    bank_guarantee = fields.Boolean(
        "Bảo lãnh ngân hàng", related="partner_id.bank_guarantee", store=True
    )
    discount_bank_guarantee = fields.Float(
        "Bảo lãnh ngân hàng", compute="_compute_discount", store=True, copy=False
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
            record._reset_discount_values()

            # [!] Kiểm tra có là Đại Lý hay Đại lý vùng trắng không?
            is_partner_agency = record.partner_id.is_agency
            # if self.field_exists("res.partner", "is_white_agency"):
            #     # The field exists, it's safe to access it
            #     is_partner_agency_white_place = record.partner_id.is_white_agency
            # else:
            #     # The field does not exist, handle accordingly
            #     is_partner_agency_white_place = False

            # if is_partner_agency_white_place:
            #     record.check_discount_10 = False
            #     record.check_discount_agency_white_place = is_partner_agency_white_place
            # else:
            # [!] Kiểm tra xem thỏa điều kiện để mua đủ trên 10 lốp xe continental
            if is_partner_agency and len(record.order_line) > 0:
                record.check_discount_10 = record._check_discount_applicable()

            # Tính tổng tiền giá sản phẩm không bao gồm hàng dịch vụ,
            # tính giá gốc ban đầu, không bao gồm thuế phí
            if len(record.order_line) > 0:
                record._calculate_discount_values()

                # Nếu đơn hàng không còn lốp xe nữa thì xóa:
                # - "Chiết Khấu Tháng" (CKT)
                # - "Chiết Khấu Bảo Lãnh" (CKBL)
                record._handle_discount_lines()

    def _reset_discount_values(self):
        self.check_discount_10 = False
        self.total_price_no_service = 0
        self.total_price_discount = 0
        self.percentage = 0
        self.total_price_after_discount = 0
        self.total_price_discount_10 = 0
        self.total_price_after_discount_10 = 0
        self.after_discount_bank_guarantee = 0
        self.bonus_max = 0
        self.discount_bank_guarantee = 0
        self.total_price_after_discount_month = 0

    def _check_discount_applicable(self):
        order_line = self.order_line.filtered(
            lambda sol: sol.product_id.detailed_type == "product"
            and self.check_category_product(sol.product_id.categ_id)
        )
        return (
            len(order_line) >= 1
            and sum(order_line.mapped("product_uom_qty")) >= DISCOUNT_QUANTITY_THRESHOLD
        )

    def _calculate_discount_values(self):
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
            if self.discount_bank_guarantee > 0:
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

        # [!] Tính chiết khấu cho Đại lý vùng trắng
        # if self.check_discount_agency_white_place:
        #     self.create_discount_agency_white_place()

        self.bonus_max = (
            self.total_price_no_service
            - self.total_price_discount
            - self.total_price_discount_10
            - self.discount_bank_guarantee
        ) / 2

    def _handle_discount_lines(self):
        order_line_ctk = self.order_line.filtered(
            lambda sol: sol.product_id
            and sol.product_id.default_code
            and sol.product_id.default_code in ["CKT", "CKBL"]
        )
        order_line_product = self.order_line.filtered(
            lambda sol: sol.product_id.detailed_type == "product"
        )
        if len(order_line_ctk) > 0 and len(order_line_product) == 0:
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
                order_line_id = self.order_line.filtered(
                    lambda x: x.product_id.default_code == "CKT"
                )
                if len(order_line_id) == 0:
                    product_tmpl_id = self.env["product.template"].search(
                        [("default_code", "=", "CKT")]
                    )
                    if not product_tmpl_id:
                        product_tmpl_id = (
                            self.env["product.template"]
                            .sudo()
                            .create(
                                {
                                    "name": "Chiết khấu tháng",
                                    "detailed_type": "service",
                                    "categ_id": 1,
                                    "taxes_id": False,
                                    "default_code": "CKT",
                                }
                            )
                        )
                    order_line_id = self.env["sale.order.line"].create(
                        {
                            "product_id": product_tmpl_id.product_variant_ids[0].id,
                            "order_id": self.id,
                            "product_uom_qty": 1,
                            "price_unit": 0,
                            "hidden_show_qty": True,
                            "code_product": "CKT",
                        }
                    )
                    _logger.info("Created discount line for partner.")
            if len(order_line_id) > 0:
                order_line_id.write(
                    {
                        "price_unit": -total_bonus,
                    }
                )
            self.write({"bonus_order": total_bonus})
            self.partner_id.write({"amount": self.partner_id.amount - bonus})
        except Exception as e:
            _logger.error("Failed to compute discount for partner: %s", e)
            pass

    def action_compute_discount_month(self):
        if not self.order_line:
            return

        self._update_programs_and_rewards()
        self._auto_apply_rewards()

        # [!] Thêm chiết khấu bảo lãnh ngân hàng
        self._handle_bank_guarantee_discount()

        # [!] Thêm chiết khấu cho Đại lý vùng trắng
        self._handle_agency_white_place_discount()

        quantity_change = self._calculate_quantity_change()

        discount_order_lines, delivery_order_lines = self._filter_order_lines()

        if not delivery_order_lines:
            return self.action_open_delivery_wizard()

        self._handle_quantity_change(
            quantity_change, discount_order_lines, delivery_order_lines
        )

        return self._handle_discount_confirmation()

    def create_discount_bank_guarantee(self):
        order_line = self.order_line.filtered(
            lambda x: x.product_id.detailed_type == "product"
            and x.order_id.check_category_product(x.product_id.categ_id)
        )
        if len(order_line) > 0:
            order_line_id = self.order_line.filtered(lambda x: x.code_product == "CKBL")
            if len(order_line_id) == 0:
                product_tmpl_id = self.env["product.template"].search(
                    [("default_code", "=", "CKBL")]
                )
                if not product_tmpl_id:
                    product_tmpl_id = (
                        self.env["product.template"]
                        .sudo()
                        .create(
                            {
                                "name": "Chiết khấu bảo lãnh",
                                "detailed_type": "service",
                                "categ_id": 1,
                                "taxes_id": False,
                                "default_code": "CKBL",
                            }
                        )
                    )
                url = http.request.httprequest.full_path
                if (
                    url
                    and url.find("/shop/cart") > -1
                    or self._context.get("bank_guarantee", False)
                ):
                    order_line_id = self.env["sale.order.line"].create(
                        {
                            "product_id": product_tmpl_id.product_variant_ids[0].id,
                            "order_id": self.id,
                            "product_uom_qty": 1,
                            "price_unit": 0,
                            "hidden_show_qty": True,
                            "code_product": "CKBL",
                        }
                    )
            if len(order_line_id) > 0:
                order_line_id.write(
                    {
                        "price_unit": -self.total_price_after_discount
                        * self.partner_id.discount_bank_guarantee
                        / DISCOUNT_PERCENTAGE_DIVISOR,
                    }
                )

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
        try:
            order_line = self.order_line.filtered(
                lambda sol: sol.product_id.detailed_type == "product"
            )
            discount_quantity_required = (
                self.env["mv.white.place.discount.line"]
                .search(
                    [("parent_id", "=", self.partner_id.discount_id.id)],
                    limit=1,
                )
                .quantity
            )
            discount_for_white_place = (
                self.env["mv.white.place.discount.line"]
                .search(
                    [("parent_id", "=", self.partner_id.discount_id.id)],
                    limit=1,
                )
                .discount
            )
            if len(order_line) > 0:
                order_line_id = self.order_line.filtered(
                    lambda sol: sol.code_product == "CKSLVT"
                )
                if len(order_line_id) == 0:
                    product_tmpl_id = self.env["product.template"].search(
                        [("default_code", "=", "CKSLVT")]
                    )
                    if not product_tmpl_id:
                        product_tmpl_id = (
                            self.env["product.template"]
                            .sudo()
                            .create(
                                {
                                    "name": "Chiết khấu Đại lý vùng trắng (SL tối thiểu 8 lốp) (1.5%)",
                                    "detailed_type": "service",
                                    "categ_id": 1,
                                    "taxes_id": False,
                                    "default_code": "CKSLVT",
                                }
                            )
                        )
                    current_url = http.request.httprequest.full_path
                    if (
                        current_url
                        and current_url.find("/shop/cart") > -1
                        or self._context.get(
                            "compute_discount_for_agency_white_place", False
                        )
                    ):
                        order_line_id = self.env["sale.order.line"].create(
                            {
                                "product_id": product_tmpl_id.product_variant_ids[0].id,
                                "order_id": self.id,
                                "product_uom_qty": 1,
                                "price_unit": 0,
                                "hidden_show_qty": True,
                                "code_product": "CKSLVT",
                            }
                        )
                        _logger.info("Created discount line for agency in white place.")
                if (
                    len(order_line_id) > 0
                    and sum(order_line.mapped("product_uom_qty"))
                    >= discount_quantity_required
                ):
                    order_line_id.write(
                        {
                            "price_unit": -self.total_price_after_discount
                            * discount_for_white_place
                            / 100,
                        }
                    )
        except Exception as e:
            _logger.error("Failed to create discount for agency in white place: %s", e)
            pass

    def _handle_agency_white_place_discount(self):
        if self.check_discount_agency_white_place:
            self.with_context(
                compute_discount_for_agency_white_place=True
            ).create_discount_agency_white_place()

    def _calculate_quantity_change(self):
        return sum(
            line.product_uom_qty
            for line in self.order_line
            if line.product_id.detailed_type == "product"
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
        try:
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
        except Exception as e:
            _logger.error("Failed to transition sale order back to draft state: %s", e)
            pass

    def action_confirm(self):
        if self.partner_id.is_agency:
            self.with_context(confirm=True).action_compute_discount_month()
            delivery_lines = self.order_line.filtered(lambda x: x.is_delivery)
            if not delivery_lines:
                raise UserError(_("No delivery lines found in the order."))
        try:
            return super(SaleOrder, self).action_confirm()
        except Exception as e:
            _logger.error("Failed to confirm sale order: %s", e)
            pass

    def action_cancel(self):
        """
        Handle the cancellation of a sale order.
        If there is a bonus order, add the bonus order amount back to the partner's amount.
        Reset the bonus order and quantity change to 0.
        Then call the parent class's action_cancel method.
        """
        try:
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
        except Exception as e:
            _logger.error("Failed to cancel sale order: %s", e)
            pass
