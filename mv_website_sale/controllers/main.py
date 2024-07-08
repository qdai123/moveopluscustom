# -*- coding: utf-8 -*-
import logging

from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.payment.controllers import portal as payment_portal
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

DISCOUNT_PERCENTAGE_DIVISOR = 100


class MoveoplusWebsiteSale(WebsiteSale):

    # === OVERRIDE METHODS ===#

    # /// Cart

    def _cart_values(self, **post):
        _logger.debug(f"MOVEO+ Cart Value [POST]: {post}")
        order = request.website.sale_get_order()
        discount_amount_invalid = order.partner_id.amount_currency < order.bonus_order
        discount_amount_maximum = order.bonus_max
        discount_amount_applied = (
            order.bonus_order if not discount_amount_invalid else 0.0
        )
        total_remaining = order.partner_id.amount_currency - order.bonus_order
        discount_amount_remaining = total_remaining if total_remaining > 0 else 0.0

        # /// Chiết khấu bảo lãnh ngân hàng
        total_discount_CKBL = (
            order.total_price_after_discount
            * order.partner_id.discount_bank_guarantee
            / DISCOUNT_PERCENTAGE_DIVISOR
        )
        # /// Chiết khấu Đại lý
        total_discount_agency = sum(
            order.order_line.filtered(
                lambda line: line.product_id.default_code == "CKSLL"
            ).mapped("price_unit")
        )
        # /// Chiết khấu Đại lý vùng trắng
        total_discount_white_agency = sum(
            order.order_line.filtered(
                lambda line: line.product_id.default_code == "CKSLVT"
            ).mapped("price_unit")
        )
        # /// Chiết khấu Đại lý miền Nam
        total_discount_southern_agency = sum(
            order.order_line.filtered(
                lambda line: line.product_id.default_code == "CKSLMN"
            ).mapped("price_unit")
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

    @http.route()
    def cart(self, access_token=None, revive="", **post):
        order = request.website.sale_get_order()
        order._compute_bonus()

        if order.partner_id.is_agency:
            order.partner_id.action_update_discount_amount()

        return super().cart(access_token=access_token, revive=revive, **post)

    # /// Checkout

    def checkout_values(self, order, **kw):
        res = super().checkout_values(order, **kw)

        # [>] Hide Discount Amount Input
        res["hide_discount_amount"] = True

        return res

    @http.route()
    def checkout(self, **post):
        res = super().checkout(**post)
        redirect = post.get("r", "/shop/cart")

        # [!] WARNING for buying more than 4 tires
        order = request.website.sale_get_order()
        if order.partner_id.is_agency and order.check_show_warning():
            return request.redirect("%s?show_warning=1" % redirect)

        if order.check_missing_partner_discount():
            return request.redirect("%s?missing_partner_discount=1" % redirect)

        return res

    # /// Payment

    def _get_shop_payment_values(self, order, **kwargs):
        res = super()._get_shop_payment_values(order, **kwargs)

        # Update the submit button label (use for Moveo Plus only)
        res["submit_button_label"] = "Đặt Hàng Ngay"

        # [>] Hide Discount Amount Input
        res["hide_discount_amount"] = True

        return res

    @http.route()
    def shop_payment(self, **post):
        order = request.website.sale_get_order()
        if order.bonus_order > 0:
            order.compute_discount_for_partner(0)

        return super().shop_payment(**post)

    @http.route()
    def shop_payment_confirmation(self, **post):
        return super().shop_payment_confirmation(**post)

    def _prepare_shop_payment_confirmation_values(self, order):
        res = super()._prepare_shop_payment_confirmation_values(order)

        # [>] Hide Discount Amount Input
        res["hide_discount_amount"] = True

        return res

    # === MOVEOPLUS METHODS ===#

    @http.route(
        ["/shop/apply_discount"],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def applying_partner_discount(self, discount_amount, **post):
        redirect_shop_cart = post.get("r", "/shop/cart")

        order = request.website.sale_get_order()
        order._compute_bonus()

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
                "%s?discount_amount_apply_exceeded=%s"
                % (redirect_shop_cart, discount_amount_maximum)
            )

        total_remaining = order.partner_id.amount_currency - order.bonus_order
        discount_amount_remaining = total_remaining if total_remaining > 0 else 0.0

        is_update = order.recompute_discount_agency
        # delivery_set = any(line.is_delivery for line in order.order_line)
        discount_agency_set = order.order_line._filter_discount_agency_lines(order)

        if not is_update:
            """Create SOline(s) discount according to wizard configuration"""
            if not discount_agency_set:
                order.compute_discount_for_partner(discount_amount_apply)
                order._handle_bank_guarantee_discount()
        else:
            """Update SOline(s) discount according to wizard configuration"""
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
                order._compute_bonus()

            if order.bank_guarantee:
                total_order_discount_CKBL = (
                    order.total_price_after_discount
                    * order.partner_id.discount_bank_guarantee
                    / DISCOUNT_PERCENTAGE_DIVISOR
                )
                order.order_line.filtered(
                    lambda line: line.product_id.default_code == "CKBL"
                ).write({"price_unit": -total_order_discount_CKBL})

        order.with_context(
            applying_partner_discount=True
        )._update_programs_and_rewards()
        order.with_context(applying_partner_discount=True)._auto_apply_rewards()

        return request.redirect(redirect_shop_cart)
