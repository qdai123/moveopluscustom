# -*- coding: utf-8 -*-
import logging

from odoo import http, _
from odoo.http import request
from odoo.addons.website_sale.controllers.main import WebsiteSale
from odoo.addons.payment.controllers import portal as payment_portal
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MoveoplusWebsiteSale(WebsiteSale):

    @http.route(
        ["/shop/apply_partner_bonus"],
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def apply_partner_bonus(self, bonus, **post):
        redirect = post.get("r", "/shop/cart")

        # TODO: Implement the logic to apply the bonus to the order like "web_auth_signup"

        # Check if bonus is a non-empty string
        if not bonus or not isinstance(bonus, str):
            return request.redirect("%s?invalid_bonus=1" % redirect)

        try:
            # Attempt to convert bonus to a float
            bonus_applying = float(bonus)
        except ValueError:
            # If the conversion fails, redirect with the invalid_bonus query parameter
            return request.redirect("%s?invalid_bonus=1" % redirect)

        # Check if bonus is negative
        if bonus_applying < 0:
            return request.redirect("%s?negative_bonus=1" % redirect)

        order_sudo = request.website.sale_get_order()
        partner_agency = order_sudo.partner_id.is_agency
        if bonus and partner_agency:
            bonus_max_amount = order_sudo.bonus_max
            bonus_used_amount = order_sudo.bonus_order
            bonus_remaining_amount = order_sudo.bonus_remaining

            if (bonus_remaining_amount - bonus_applying) < 0:
                return request.redirect(
                    "%s?bonus_apply_over_remaining=%s"
                    % (redirect, bonus_remaining_amount)
                )

            if (bonus_max_amount - (bonus_applying + bonus_used_amount)) < 0:
                return request.redirect(
                    "%s?bonus_apply_over_max=%s" % (redirect, bonus_max_amount)
                )

            # Re-calculate the discount for the partner
            order_sudo.compute_discount_for_partner(bonus_applying)

        return request.redirect(redirect)
