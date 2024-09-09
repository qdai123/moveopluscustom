# -*- coding: utf-8 -*-
from odoo import _, fields, models


class MvService(models.Model):
    _name = "mv.service"
    _description = _("Service")

    name = fields.Char(required=True)

    _sql_constraints = [
        ("name_unique", "UNIQUE(name)", "Mỗi một Dịch vụ phải là DUY NHẤT!")
    ]
