# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.tools.float_utils import float_compare


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # ===============================
    # ORM Methods
    # ===============================

    @api.model_create_multi
    def create(self, vals_list):
        return super(StockPicking, self).create(vals_list)

    def write(self, vals):
        return super(StockPicking, self).write(vals)

    # ===============================
    # ACTION Methods
    # ===============================

    def action_confirm(self):
        return super(StockPicking, self).action_confirm()

    def action_assign(self):
        return super(StockPicking, self).action_assign()
