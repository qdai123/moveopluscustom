# -*- coding: utf-8 -*-
from odoo.addons.sale.controllers import portal

from odoo import http
from odoo.http import request


class MoveoplusCustomerPortal(portal.CustomerPortal):

    @http.route()
    def home(self, **kw):
        res = super().home(**kw)

        user = request.env.user
        partner = user.partner_id.sudo()
        if partner:
            partner.action_update_discount_amount()

        return res
