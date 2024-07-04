# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
from odoo.addons.sale.controllers import portal


class MoveoplusCustomerPortal(portal.CustomerPortal):
    print("Hello World!")
