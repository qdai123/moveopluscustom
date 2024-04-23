# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_assign(self):
        res = super(StockPicking, self).action_assign()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        print(f"Create Picking: {vals_list}")
        return super(StockPicking, self).create(vals_list)

    def write(self, vals):
        print(f"Write Picking: {vals}")
        return super(StockPicking, self).write(vals)
