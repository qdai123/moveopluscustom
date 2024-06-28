# -*- coding: utf-8 -*-
import logging

from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.payment.controllers import portal as payment_portal
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MoveoplusWebsiteSale(WebsiteSale):

    @http.route()
    def checkout(self, **post):
        # [!] WARNING for buying more than 4 tires
        redirect = post.get("r", "/shop/cart")
        order_sudo = request.website.sale_get_order()
        if order_sudo.partner_id.is_agency and order_sudo.check_show_warning():
            return request.redirect("%s?show_warning=1" % redirect)
        return super().checkout(**post)

    @http.route()
    def cart(self, access_token=None, revive="", **post):
        try:
            order = request.website.sale_get_order()
            if order.partner_id.is_agency:
                if order.partner_id.is_white_agency:
                    order.create_discount_agency_white_place()
                if order.partner_id.bank_guarantee:
                    order.create_discount_bank_guarantee()

                order.partner_id.sudo().action_update_discount_amount()

            return super().cart(access_token=access_token, revive=revive, **post)
        except Exception as e:
            _logger.error("Unexpected error: %s", e)
            raise UserError(_("An unexpected error occurred. Please try again."))

    # ------------------------------------------------------
    # Payment (OVERRIDE)
    # ------------------------------------------------------

    def _get_shop_payment_values(self, order: "sale.order", **kwargs):
        """
        Get the payment values for the shop.

        :param order: The sale order.
        :param kwargs: Additional keyword arguments.
        :return: A dictionary containing the payment values.
        """
        try:
            # Call the parent method
            res = super()._get_shop_payment_values(order, **kwargs)

            # Update the submit button label (use for Moveo Plus only)
            res["submit_button_label"] = "Đặt Hàng Ngay"

            return res
        except Exception as e:
            _logger.error("Unexpected error: %s", e)
            raise UserError(_("An unexpected error occurred. Please try again."))

    @http.route()
    def shop_payment(self, **post):
        """
        Compute the discount for a partner if the order bonus is greater than 0,
        and then call the parent method.

        :param post: Additional keyword arguments.
        :return: A werkzeug.wrappers.Response object.
        """
        try:
            order = request.website.sale_get_order()
            if order.bonus_order > 0:
                order.compute_discount_for_partner(0)
            return super().shop_payment(**post)
        except Exception as e:
            _logger.error("Unexpected error: %s", e)
            raise UserError(_("An unexpected error occurred. Please try again."))
