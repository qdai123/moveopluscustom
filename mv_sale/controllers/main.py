# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleMvSale(WebsiteSale):
    @http.route(
        ["/shop/checkout"], type="http", auth="public", website=True, sitemap=False
    )
    def checkout(self, **post):
        # Cảnh báo mua trên 4 lốp xe
        redirect = post.get("r", "/shop/cart")
        order_sudo = request.website.sale_get_order()
        if order_sudo.partner_id.is_agency:
            if order_sudo.check_show_warning():
                return request.redirect("%s?show_warning=1" % redirect)
        return super().checkout(**post)

    @http.route(
        ["/shop/compute_bonus_amount"],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def compute_bonus_amount(self, bonus, **post):
        redirect = post.get("r", "/shop/cart")
        # empty promo code is used to reset/remove pricelist (see `sale_get_order()`)
        if bonus:
            try:
                bonus = int(bonus)
            except:
                return request.redirect("%s?not_available_condition=1" % redirect)
            order_sudo = request.website.sale_get_order()
            if order_sudo.partner_id.is_agency:
                total_bonus = order_sudo.compute_discount_for_partner(bonus)
                try:
                    # tổng tiền muốn áp dụng đã vượt qua tài khoản hiện có
                    if total_bonus > order_sudo.partner_id.amount:
                        return request.redirect(
                            "%s?bonus_larger_partner=%s" % (redirect, total_bonus)
                        )
                    # tổng tiền muốn áp dụng đã vượt qua tài khoản hiện có
                    if total_bonus > 0:
                        return request.redirect(
                            "%s?bonus_more_time=%s" % (redirect, total_bonus)
                        )
                except:
                    pass
        return request.redirect(redirect)

    @http.route(["/shop/cart"], type="http", auth="public", website=True, sitemap=False)
    def cart(self, access_token=None, revive="", **post):
        order = request.website.sale_get_order()
        if order.partner_id.bank_guarantee:
            order.create_discount_bank_guarantee()
        return super().cart(access_token=access_token, revive=revive, **post)

    @http.route(
        "/shop/payment", type="http", auth="public", website=True, sitemap=False
    )
    def shop_payment(self, **post):
        order = request.website.sale_get_order()
        if order.bonus_order > 0:
            order.compute_discount_for_partner(0)
        return super().shop_payment(**post)

    def _get_shop_payment_values(self, order, **kwargs):
        res = super(WebsiteSaleMvSale, self)._get_shop_payment_values(order, **kwargs)
        res["submit_button_label"] = "Đặt Hàng Ngay"
        return res
