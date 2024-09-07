# -*- coding: utf-8 -*-
from odoo import _, fields, models


class MvServiceDetail(models.Model):
    _name = "mv.service.detail"
    _description = _("Service Detail")

    vnd_currency_id = fields.Many2one(
        "res.currency",
        "Tiền tệ (VNĐ)",
        default=lambda self: self.env["res.currency"].search(
            [("name", "=", "VND")], limit=1
        ),
    )
    name = fields.Char("Dịch vụ", required=True)
    service_price = fields.Float("Giá dịch vụ/ doanh thu trung bình (VNĐ)")
    notes = fields.Text("Ghi chú")

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "Mỗi một Hãng lốp/Thương hiệu phải là DUY NHẤT!",
        )
    ]
