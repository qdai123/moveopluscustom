# -*- coding: utf-8 -*-
from odoo import _, fields, models


class MvServiceDetail(models.Model):
    _name = "mv.service.detail"
    _description = _("Service Detail")
    _rec_name = "mv_service_id"

    partner_survey_id = fields.Many2one(
        "mv.partner.survey",
        "Phiếu khảo sát",
        required=True,
        index=True,
        ondelete="restrict",
    )
    mv_service_id = fields.Many2one("mv.service", index=True)
    service_price = fields.Float("Giá dịch vụ/Doanh thu trung bình (VNĐ)")
    vnd_currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env["res.currency"].search(
            [("name", "=", "VND")], limit=1
        ),
    )
    notes = fields.Text("Ghi chú")
