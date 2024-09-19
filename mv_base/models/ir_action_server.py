# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class MVIrActionServer(models.Model):
    _inherit = "ir.actions.server"

    code = fields.Text(groups='base.group_system,sales_team.group_sale_salesman')
