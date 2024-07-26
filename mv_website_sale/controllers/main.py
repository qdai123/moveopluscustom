# -*- coding: utf-8 -*-
import logging

from odoo.addons.website_sale.controllers.main import WebsiteSale

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

DISCOUNT_PERCENTAGE_DIVISOR = 100


class MoveoplusWebsiteSale(WebsiteSale):

    # === MOVEOPLUS OVERRIDE ===#

    # /// CART

    @http.route()
    def cart(self, **post):
        """
        Handle the cart view, compute necessary discounts and bonuses, and update the partner's discount amount if applicable.

        :param post: Dictionary containing POST data.
        :return: The result of the parent class's cart method.
        """
        _logger.debug(f">>> Cart [POST]: {post} <<<")

        try:
            order = request.website.sale_get_order()
            if not order:
                _logger.error("No order found.")
                return request.redirect("/shop/cart")

            # Compute partner bonus and bonus order line
            order.sudo()._compute_partner_bonus()
            order.sudo()._compute_bonus_order_line()

            # If the partner is an agency, update the partner's discount amount
            if order.partner_id.is_agency:
                order.sudo().partner_id.action_update_discount_amount()

            # Call the parent class's cart method
            return super(MoveoplusWebsiteSale, self).cart(**post)

        except Exception as e:
            _logger.error(f"Error in cart method: {e}")
            return request.redirect("/shop/cart")

    def _cart_values(self, **post):
        """
        Calculate and return various discount-related values for the current cart.

        :param post: Dictionary containing POST data.
        :return: Dictionary with calculated discount values.
        """
        _logger.debug(f">>> MOVEO+ Cart Value [POST]: {post} <<<")

        order = request.website.sale_get_order()
        if not order:
            _logger.error("No order found.")
            return {}

        discount_amount_invalid = order.partner_id.amount_currency < order.bonus_order
        discount_amount_maximum = order.bonus_max
        discount_amount_applied = (
            order.bonus_order if not discount_amount_invalid else 0.0
        )
        total_remaining = order.partner_id.amount_currency - order.bonus_order
        discount_amount_remaining = total_remaining if total_remaining > 0 else 0.0

        total_discount_CKBL = self._calculate_bank_guarantee_discount(order)
        total_discount_agency = self._calculate_agency_discount(order, "CKSLL")
        total_discount_white_agency = self._calculate_agency_discount(order, "CKSLVT")
        total_discount_southern_agency = self._calculate_agency_discount(
            order, "CKSLMN"
        )

        values_update = {
            "is_update": order.recompute_discount_agency,
            "delivery_set": any(line.is_delivery for line in order.order_line),
            "discount_agency_set": order.order_line._filter_discount_agency_lines(
                order
            ),
            "discount_amount_invalid": discount_amount_invalid,
            "discount_amount_maximum": discount_amount_maximum,
            "discount_amount_remaining": discount_amount_remaining,
            "discount_amount_applied": (
                -discount_amount_applied if discount_amount_applied > 0 else 0.0
            ),
            "bank_guarantee_set": order.bank_guarantee,
            "total_discount_CKBL": (
                -total_discount_CKBL if total_discount_CKBL > 0 else 0.0
            ),
            "partner_agency_set": order.partner_agency,
            "total_discount_agency": (
                -total_discount_agency if total_discount_agency > 0 else 0.0
            ),
            "partner_white_agency_set": order.partner_white_agency,
            "total_discount_white_agency": (
                -total_discount_white_agency if total_discount_white_agency > 0 else 0.0
            ),
            "partner_southern_agency_set": order.partner_southern_agency,
            "total_discount_southern_agency": (
                -total_discount_southern_agency
                if total_discount_southern_agency > 0
                else 0.0
            ),
        }

        return values_update

    def _calculate_bank_guarantee_discount(self, order):
        """
        Calculate the bank guarantee discount for the order.

        :param order: The current sale order.
        :return: The calculated bank guarantee discount.
        """
        return (
            order.total_price_after_discount
            * order.partner_id.discount_bank_guarantee
            / DISCOUNT_PERCENTAGE_DIVISOR
        )

    def _calculate_agency_discount(self, order, product_code):
        """
        Calculate the agency discount for the order based on the product code.

        :param order: The current sale order.
        :param product_code: The product code to filter the discount lines.
        :return: The calculated agency discount.
        """
        return sum(
            order.order_line.filtered(
                lambda line: line.product_id.default_code == product_code
            ).mapped("price_unit")
        )

    # /// CHECKOUT

    @http.route()
    def checkout(self, **post):
        """
        Handle the checkout process, including checking for warnings and missing partner discounts.

        :param post: Dictionary containing POST data.
        :return: The result of the parent class's checkout method.
        """
        _logger.debug(f">>> Checkout [POST]: {post} <<<")

        try:
            redirect = post.get("r", "/shop/cart")
            order = request.website.sale_get_order()
            if not order:
                _logger.error("No order found.")
                return request.redirect(redirect)

            # Check if the partner is an agency and if a warning should be shown
            if order.partner_id.is_agency and order.check_show_warning():
                return request.redirect(f"{redirect}?show_warning=1")

            # Check if the partner discount line is missing
            if order.check_missing_partner_discount():
                return request.redirect(f"{redirect}?missing_partner_discount=1")

            # Call the parent class's checkout method
            return super(MoveoplusWebsiteSale, self).checkout(**post)

        except Exception as e:
            _logger.error(f"Error in checkout method: {e}")
            return request.redirect("/shop/cart")

    def checkout_values(self, order, **kw):
        vals = super().checkout_values(order, **kw)

        # [>] ADDITIONAL VALUES 'hide_discount_amount'
        vals["hide_discount_amount"] = True

        return vals

    # /// PAYMENT

    @http.route()
    def shop_payment(self, **post):
        """
        Handle the shop payment process, including computing discounts for the partner if applicable.

        :param post: Dictionary containing POST data.
        :return: The result of the parent class's shop_payment method.
        """
        _logger.debug(f">>> Shop Payment [POST]: {post} <<<")

        try:
            order = request.website.sale_get_order()
            if not order:
                _logger.error("No order found.")
                return request.redirect("/shop/cart")

            # If the order has a bonus, compute the discount for the partner
            if order.bonus_order > 0:
                order.compute_discount_for_partner(0)

            # Call the parent class's shop_payment method
            return super(MoveoplusWebsiteSale, self).shop_payment(**post)

        except Exception as e:
            _logger.error(f"Error in shop_payment method: {e}")
            return request.redirect("/shop/cart")

    def _get_shop_payment_values(self, order, **kwargs):
        vals = super()._get_shop_payment_values(order, **kwargs)

        # Update the submit button label (use for Moveo Plus only)
        vals["submit_button_label"] = "Đặt Hàng Ngay"

        # [>] ADDITIONAL VALUES 'hide_discount_amount'
        vals["hide_discount_amount"] = True

        return vals

    def _prepare_shop_payment_confirmation_values(self, order):
        vals = super()._prepare_shop_payment_confirmation_values(order)

        # [>] ADDITIONAL VALUES 'hide_discount_amount'
        vals["hide_discount_amount"] = True

        return vals

    # === MOVEOPLUS METHODS ===#

    @http.route(
        "/shop/apply_discount", type="http", auth="public", website=True, sitemap=False
    )
    def applying_partner_discount(self, discount_amount, **post):
        """
        Apply the partner discount to the current order.

        :param discount_amount: The amount of discount to apply.
        :param post: Dictionary containing POST data.
        :return: Redirect to the shop cart.
        """
        _logger.debug(
            f">>> Applying Partner Discount [POST]: {post}, discount_amount: {discount_amount} <<<"
        )

        redirect_shop_cart = post.get("r", "/shop/cart")
        order = request.website.sale_get_order()
        if not order:
            _logger.error("No order found.")
            return request.redirect(redirect_shop_cart)

        # Compute necessary discounts and bonuses
        order.sudo()._compute_partner_bonus()
        order.sudo()._compute_bonus_order_line()

        discount_amount_apply = float(discount_amount)
        if discount_amount_apply < 0:
            return request.redirect(redirect_shop_cart)

        discount_amount_invalid = order.partner_id.amount_currency < order.bonus_order
        discount_amount_maximum = order.bonus_max
        discount_amount_applied = (
            order.bonus_order if not discount_amount_invalid else 0.0
        )
        total_applied = discount_amount_apply + discount_amount_applied

        if (
            discount_amount_applied == 0
            and discount_amount_apply > discount_amount_maximum
        ) or (discount_amount_applied != 0 and total_applied > discount_amount_maximum):
            return request.redirect(
                f"{redirect_shop_cart}?discount_amount_apply_exceeded={discount_amount_maximum}"
            )

        total_remaining = order.partner_id.amount_currency - order.bonus_order
        discount_amount_remaining = total_remaining if total_remaining != 0 else 0.0

        is_update = order.recompute_discount_agency
        discount_agency_set = order.order_line._filter_discount_agency_lines(order)

        if not is_update:
            # Create SOline(s) discount according to wizard configuration
            if not discount_agency_set:
                order.compute_discount_for_partner(discount_amount_apply)
        else:
            # Update SOline(s) discount according to wizard configuration
            if discount_agency_set:
                total_order_discount_CKT = (
                    (discount_amount_apply + discount_amount_applied)
                    if discount_amount_remaining > 0
                    else discount_amount_apply
                )
                order.order_line.filtered(
                    lambda line: line.product_id.default_code == "CKT"
                ).write(
                    {
                        "price_unit": (
                            -total_order_discount_CKT
                            if total_order_discount_CKT > 0
                            else 0.0
                        )
                    }
                )
                order._compute_partner_bonus()
                order._compute_bonus_order_line()

        order.with_context(
            applying_partner_discount=True
        )._update_programs_and_rewards()
        order.with_context(applying_partner_discount=True)._auto_apply_rewards()

        return request.redirect(redirect_shop_cart)
