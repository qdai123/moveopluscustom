# -*- coding: utf-8 -*-
from odoo import api, models
from odoo.osv import expression


class PickingType(models.Model):
    _inherit = "stock.picking.type"

    @api.model
    def web_search_read(
        self,
        domain,
        specification,
        offset=0,
        limit=None,
        order=None,
        count_limit=None,
    ):
        # [!] Filter by Warehouse's Stock Users Access
        if self.user_has_groups("stock.group_stock_user") and not self.user_has_groups(
            "stock.group_stock_manager"
        ):
            domain = expression.AND(
                [
                    domain,
                    [
                        "|",
                        ("warehouse_id.stock_users_access_ids", "in", self.env.user.id),
                        ("warehouse_id.stock_users_access_ids", "=", False),
                    ],
                ]
            )

        return super(PickingType, self).web_search_read(
            domain,
            specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )
