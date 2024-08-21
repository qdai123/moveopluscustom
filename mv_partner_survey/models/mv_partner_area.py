# -*- coding: utf-8 -*-
from odoo import _, fields, models


class MvPartnerArea(models.Model):
    _name = "mv.partner.area"
    _description = _("Area")

    parent_id = fields.Many2one("mv.partner.area", "Vùng cha", index=True)
    name = fields.Char("Tên vùng", required=True)
    code_area = fields.Char("Mã vùng")

    _sql_constraints = [
        (
            "name_code_unique",
            "unique(name, code)",
            "Tên vùng và mã vùng phải là DUY NHẤT!",
        )
    ]
