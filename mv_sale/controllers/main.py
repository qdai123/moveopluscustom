# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale


class WebsiteSaleMvSale(WebsiteSale):
    @http.route(['/shop/checkout'], type='http', auth="public", website=True, sitemap=False)
    def checkout(self, **post):
        # cảnh báo mua trên 4 lốp xe
        redirect = post.get('r', '/shop/cart')
        order_sudo = request.website.sale_get_order()
        if order_sudo.partner_id.is_agency:
            if order_sudo.check_show_warning():
                return request.redirect("%s?show_warning=1" % redirect)
        return super().checkout(**post)

    @http.route(['/shop/compute_bonus_amount'], type='http', auth="public", website=True, sitemap=False)
    def compute_bonus_amount(self, bonus, **post):
        redirect = post.get('r', '/shop/cart')
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
                        return request.redirect("%s?bonus_larger_partner=%s" % (redirect, total_bonus))
                    # tổng tiền muốn áp dụng đã vượt qua tài khoản hiện có
                    if total_bonus > 0:
                        return request.redirect("%s?bonus_more_time=%s" % (redirect, total_bonus))
                except:
                    pass
        return request.redirect(redirect)
