# -*- coding: utf-8 -*-
from datetime import date, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MvWarrantyDiscountPolicy(models.Model):
    _name = "mv.warranty.discount.policy"
    _description = _("MOVEO PLUS Warranty Discount Policy")
    _order = "date_from desc, date_to desc"

    active = fields.Boolean("Active", default=True)
    name = fields.Char(compute="_compute_name", store=True, readonly=False)
    date_from = fields.Date(default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(
        default=lambda self: (date.today().replace(day=1) + timedelta(days=32)).replace(
            day=1
        )
        - timedelta(days=1)
    )
    policy_status = fields.Selection(
        selection=[
            ("open", "Mới"),
            ("applying", "Đang Áp Dụng"),
            ("close", "Đóng"),
        ],
        string="Status",
        default="open",
    )
    product_attribute_ids = fields.Many2many("product.attribute")
    line_ids = fields.One2many(
        "mv.warranty.discount.policy.line", "warranty_discount_policy_id"
    )
    partner_ids = fields.Many2many(
        "mv.discount.partner", domain=[("partner_id.is_agency", "=", True)]
    )

    def action_reset_to_open(self):
        self.ensure_one()
        self.write({"policy_status": "open"})

    def action_apply(self):
        self.ensure_one()
        if self.policy_status == "open":
            self.write({"policy_status": "applying"})

        return True

    def action_close(self):
        self.ensure_one()
        if self.policy_status == "applying":
            self.write({"policy_status": "close"})

        return True

    @api.depends("date_from", "date_to")
    def _compute_name(self):
        for record in self:
            policy_name = "Chính sách chiết khấu kích hoạt"
            date_from = record.date_from
            date_to = record.date_to

            if date_from and date_to:
                if date_from.year == date_to.year:
                    if date_from.month == date_to.month:
                        record.name = (
                            f"{policy_name} (tháng {date_from.month}/{date_from.year})"
                        )
                    else:
                        record.name = f"{policy_name} (từ {date_from.month}/{date_from.year} đến {date_to.month}/{date_to.year})"
                else:
                    record.name = policy_name
            else:
                record.name = policy_name

    @api.onchange("date_from")
    def _onchange_date_from(self):
        if self.date_from:
            self.date_to = (self.date_from + timedelta(days=32)).replace(
                day=1
            ) - timedelta(days=1)

    @api.model_create_multi
    def create(self, vals_list):
        res = super(MvWarrantyDiscountPolicy, self).create(vals_list)

        if res:
            for record in res:
                if not record.partner_ids:
                    partner_ids = self.env["mv.discount.partner"].search(
                        [("partner_id.is_agency", "=", True)]
                    )
                    record.partner_ids = [(6, 0, partner_ids.ids)]
                    for partner in partner_ids:
                        partner.write(
                            {"warranty_discount_policy_ids": [(4, record.id)]}
                        )

        return res

    def write(self, vals):
        res = super().write(vals)

        if res:
            for record in self:
                if record.partner_ids:
                    for partner in record.partner_ids:
                        partner.write(
                            {"warranty_discount_policy_ids": [(6, 0, record.ids)]}
                        )

        return res

    @api.constrains("date_from", "date_to")
    def _validate_already_exist_policy(self):
        for record in self:
            if record.date_from and record.date_to:
                record_exists = self.env["mv.warranty.discount.policy"].search_count(
                    [
                        ("id", "!=", record.id),
                        ("active", "=", True),
                        ("date_from", ">=", record.date_from),
                        ("date_to", "<=", record.date_to),
                    ]
                )
                if record_exists > 0:
                    raise ValidationError(
                        _("Chính sách này đã bị trùng, vui lòng kiểm tra lại!")
                    )


class MvWarrantyDiscountPolicyLine(models.Model):
    _name = _description = "mv.warranty.discount.policy.line"

    warranty_discount_policy_id = fields.Many2one(
        "mv.warranty.discount.policy",
        domain=[("active", "=", True)],
        readonly=True,
        help="Parent Model: mv.warranty.discount.policy",
    )
    currency_id = fields.Many2one(
        "res.currency", default=lambda self: self.env.company.currency_id
    )
    quantity_from = fields.Integer("Số lượng Min", default=0)
    quantity_to = fields.Integer("Số lượng Max", default=0)
    discount_amount = fields.Monetary("Số tiền chiết khấu", digits=(16, 2))
    explanation = fields.Text("Diễn giải")
