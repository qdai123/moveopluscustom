# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class StockQuant(models.Model):
    _inherit = "stock.quant"

    inventory_period_id = fields.Many2one(
        related="lot_id.inventory_period_id", store=True
    )
