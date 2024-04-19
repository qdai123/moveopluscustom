# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.model_create_multi
    def create(self, vals_list):
        import pprint

        print("Create Stock Picking")
        pprint.pprint(vals_list, indent=4)
        return super(StockPicking, self).create(vals_list)

    def write(self, vals):
        import pprint

        print("Write Stock Picking")
        pprint.pprint(vals, indent=4)
        return super(StockPicking, self).write(vals)
