# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class MvDiscountPolicyPartnerHistory(models.Model):
    _name = "mv.discount.partner.history"
    _description = _("MO+ Discount Policy for Partner (History)")
    _rec_name = "history_description"

    # === FIELDS ===#
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Đại lý",
        domain=[("is_agency", "=", True)],
    )
    partner_currency_id = fields.Many2one(
        comodel_name="res.currency", related="partner_id.currency_id"
    )
    is_waiting_approval = fields.Boolean(string="Đang chờ duyệt", default=False)
    is_positive_money = fields.Boolean(string="Là chiết khấu dương", default=False)
    is_negative_money = fields.Boolean(string="Là chiết khấu âm", default=False)
    total_money = fields.Monetary(
        string="Tổng tiền", digits=(16, 2), currency_field="partner_currency_id"
    )
    total_money_discount_display = fields.Char(string="Số tiền chiết khấu (+/-)")
    history_description = fields.Char(string="Diễn giải/Hành động", readonly=True)
    # === ĐƠN HÀNG ÁP DỤNG CHIẾT KHẤU ===
    sale_order_id = fields.Many2one(
        comodel_name="sale.order", string="Đơn hàng chiết khấu"
    )
    sale_order_discount_money_apply = fields.Monetary(
        string="Tiền chiết khấu áp dụng",
        currency_field="partner_currency_id",
        digits=(16, 2),
    )
    # === CHÍNH SÁCH CHIẾT KHẤU SẢN LƯỢNG ===
    production_discount_policy_id = fields.Many2one(
        string="Chính sách Chiết Khấu Sản Lượng",
        comodel_name="mv.compute.discount.line",
        domain=[("parent_id", "!=", False), ("partner_id", "=", partner_id)],
    )
    production_discount_policy_total_money = fields.Monetary(
        string="Tiền CKSL",
        currency_field="partner_currency_id",
        digits=(16, 2),
    )
    # === CHÍNH SÁCH CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH ===
    warranty_discount_policy_id = fields.Many2one(
        string="Chính sách Chiết Khấu Kích Hoạt Bảo Hành",
        comodel_name="mv.discount",
        domain=[("parent_id", "!=", False), ("partner_id", "=", partner_id)],
    )
    warranty_discount_policy_total_money = fields.Monetary(
        string="Tiền CKKHBH",
        currency_field="partner_currency_id",
        digits=(16, 2),
    )

    @api.model
    def _create_history_line(self, partner_id, history_description, **kwargs):
        return self.create(
            {
                "partner_id": partner_id,
                "history_description": history_description,
                **kwargs,
            }
        )
