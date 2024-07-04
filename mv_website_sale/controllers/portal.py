# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.sale.controllers import portal


class MoveoplusCustomerPortal(portal.CustomerPortal):

    @http.route()
    def home(self, **kw):
        res = super().home(**kw)

        user = request.env.user
        partner = (
            request.env["res.partner"]
            .sudo()
            .search([("id", "=", user.partner_id.id)], limit=1)
        )
        if partner:
            partner.action_update_discount_amount()

        return res
