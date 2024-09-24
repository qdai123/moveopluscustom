# -*- coding: utf-8 -*-
from odoo import api, fields, models


class Warehouse(models.Model):
    _inherit = "stock.warehouse"

    allow_stock_users_access = fields.Boolean("Allow Stock Users Access", default=False)
    stock_users_access_ids = fields.Many2many(
        comodel_name="res.users",
        relation="stock_warehouse_user_rel",
        column1="warehouse_id",
        column2="user_id",
        domain=lambda self: [
            ("groups_id", "in", self.env.ref("stock.group_stock_user").id),
            ("groups_id", "not in", self.env.ref("stock.group_stock_manager").id),
        ],
        string="Stock Users",
    )

    def load_stock_users_access(self):
        self.ensure_one()
        stock_users = self.env["res.users"].search(
            [
                ("groups_id", "=", self.env.ref("stock.group_stock_user").id),
                ("groups_id", "not in", self.env.ref("stock.group_stock_manager").id),
            ]
        )
        self.stock_users_access_ids = [(6, 0, stock_users.ids)]
        self.env.cr.commit()

    def refresh_stock_users_access(self):
        self.mapped("stock_users_access_ids").invalidate_cache()
        return True
