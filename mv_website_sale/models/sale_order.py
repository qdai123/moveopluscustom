# -*- coding: utf-8 -*-
from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # ==================================
    # ORM / CURD Methods
    # ==================================

    def copy(self, default=None):
        # MOVEOPLUS Override
        orders = super(SaleOrder, self).copy(default)
        orders._update_programs_and_rewards()
        orders._auto_apply_rewards()
        return orders
