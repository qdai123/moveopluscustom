# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


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
        comodel_name="res.currency",
        related="partner_id.currency_id",
    )
    is_waiting_approval = fields.Boolean(string="C/k đang chờ duyệt", default=False)
    is_positive_money = fields.Boolean(string="C/k Dương", default=False)
    is_negative_money = fields.Boolean(string="C/k Âm", default=False)
    total_money = fields.Monetary(
        string="Tổng tiền",
        currency_field="partner_currency_id",
        digits=(16, 2),
    )
    total_money_discount_display = fields.Char(string="Số tiền chiết khấu (+/-)")
    history_description = fields.Char(string="Diễn giải/Hành động", readonly=True)
    history_date = fields.Datetime(
        string="Ngày ghi nhận",
        default=lambda self: fields.Datetime.now(),
        readonly=True,
    )
    history_user_action_id = fields.Many2one(
        comodel_name="res.users", string="Người thực hiện"
    )
    # === ĐƠN HÀNG ÁP DỤNG CHIẾT KHẤU ===
    sale_order_id = fields.Many2one(
        comodel_name="sale.order", string="Đơn hàng chiết khấu"
    )
    sale_order_state = fields.Char(string="Trạng thái đơn hàng")
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
        comodel_name="mv.compute.warranty.discount.policy.line",
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


class MvPartnerTotalDiscountDetailsHistory(models.Model):
    _name = "mv.partner.total.discount.detail.history"
    _description = _("MO+ Partner Total Discount Detail (History)")
    _rec_name = "description"

    # === FIELDS ===#
    parent_id = fields.Many2one(
        comodel_name="mv.compute.discount",
        readonly=True,
        ondelete="set null",
        index=True,
    )
    policy_line_id = fields.Many2one(
        comodel_name="mv.compute.discount.line",
        string="Chính sách CKSL",
        readonly=True,
        help="Chính sách Chiết Khấu Sản Lượng",
    )
    partner_id = fields.Many2one("res.partner", "Đại lý", readonly=True)
    description = fields.Text("Diễn giải", readonly=True)
    total_discount_amount_display = fields.Char("Tiền chiết khấu (+/-)", readonly=True)
    total_discount_amount = fields.Float("Tiền chiết khấu", readonly=True)

    @api.model
    def _create_total_discount_detail_history_line(self, parent_id, policy_id):
        total_discount_lines = {}
        if policy_id:
            compute_date = (
                policy_id.parent_id and policy_id.parent_id.report_date or False
            )
            month = compute_date.month
            year = compute_date.year

            # === CHIẾT KHẤU KHUYẾN KHÍCH ===
            if policy_id.is_promote_discount and policy_id.promote_discount_money > 0:
                total_discount_lines["promote_in_month"] = {
                    "description": f"Chiết khấu khuyến khích tháng {policy_id.name}",
                    "total_discount_amount_display": (
                        "+ {:,.2f}".format(policy_id.promote_discount_money)
                        if policy_id.promote_discount_money > 0
                        else "{:,.2f}".format(policy_id.promote_discount_money)
                    ),
                    "total_discount_amount": policy_id.promote_discount_money,
                }
            # === CHIẾT KHẤU THÁNG (1 THÁNG) ===
            if policy_id.month and policy_id.month_money > 0:
                total_discount_lines["one_month"] = {
                    "description": f"Chiết khấu tháng, tháng {policy_id.name}",
                    "total_discount_amount_display": (
                        "+ {:,.2f}".format(policy_id.month_money)
                        if policy_id.month_money > 0
                        else "{:,.2f}".format(policy_id.month_money)
                    ),
                    "total_discount_amount": policy_id.month_money,
                }
            # === CHIẾT KHẤU THÁNG (2 THÁNG) ===
            if policy_id.two_month and policy_id.two_money > 0:
                current_month = month
                previous_month = current_month - 1 if current_month > 1 else 12
                total_discount_lines["two_months"] = {
                    "description": f"Chiết khấu 2 tháng, tháng {previous_month}-{current_month}/{year}",
                    "total_discount_amount_display": (
                        "+ {:,.2f}".format(policy_id.two_money)
                        if policy_id.two_money > 0
                        else "{:,.2f}".format(policy_id.two_money)
                    ),
                    "total_discount_amount": policy_id.two_money,
                }
            # === CHIẾT KHẤU QUÝ ===
            if policy_id.quarter and policy_id.quarter_money > 0:
                if 1 <= month <= 3:
                    quarter = 1
                elif 4 <= month <= 6:
                    quarter = 2
                elif 7 <= month <= 9:
                    quarter = 3
                elif 10 <= month <= 12:
                    quarter = 4
                else:
                    _logger.error(f"Month {month} is invalid")
                    quarter = False

                total_discount_lines["quarter"] = {
                    "description": f"Chiết khấu quý {quarter} năm {year}",
                    "total_discount_amount_display": (
                        "+ {:,.2f}".format(policy_id.quarter_money)
                        if policy_id.quarter_money > 0
                        else "{:,.2f}".format(policy_id.quarter_money)
                    ),
                    "total_discount_amount": policy_id.quarter_money,
                }
            # === CHIẾT KHẤU NĂM ===
            if policy_id.year and policy_id.year_money > 0:
                total_discount_lines["year"] = {
                    "description": f"Chiết khấu năm {year}",
                    "total_discount_amount_display": (
                        "+ {:,.2f}".format(policy_id.year_money)
                        if policy_id.year_money > 0
                        else "{:,.2f}".format(policy_id.year_money)
                    ),
                    "total_discount_amount": policy_id.year_money,
                }

        vals_list = []
        for key, value in total_discount_lines.items():
            vals = {
                "parent_id": parent_id.id,
                "policy_line_id": policy_id.id,
                "partner_id": policy_id.partner_id.id,
            }
            if key in [
                "promote_in_month",
                "one_month",
                "two_months",
                "quarter",
                "year",
            ]:
                vals.update(value)
                vals_list.append(vals)

        return self.create(vals_list)
