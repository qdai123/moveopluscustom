# -*- coding: utf-8 -*-
from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    short_name = fields.Char(related="partner_id.short_name", store=True)
