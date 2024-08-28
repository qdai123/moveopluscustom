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
    name = fields.Char("Dịch vụ", default="NEW", required=True)
    service_price = fields.Monetary(
        "Giá dịch vụ/ doanh thu trung bình (VNĐ)",
        default=0.0,
        currency_field="vnd_currency_id",
    )
    notes = fields.Text("Ghi chú")

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "Mỗi một Hãng lốp/Thương hiệu phải là DUY NHẤT!",
        )
    ]
