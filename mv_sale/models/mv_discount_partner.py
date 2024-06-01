# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MvDiscountPolicyPartner(models.Model):
    _name = _description = "mv.discount.partner"
    _rec_name = "partner_id"

    date = fields.Date("Ngày hiệu lực", default=fields.Date.today().replace(day=1))
    level = fields.Integer("Cấp bậc", default=0)
    min_debt = fields.Integer("Min Debt", default=0)
    max_debt = fields.Integer("Max Debt", default=0)
    number_debt = fields.Float("Ratio Debt", default=0)
    # RELATION Fields
    parent_id = fields.Many2one(
        "mv.discount",
        "Chính sách chiết khấu",
        domain=[("active", "=", True)],
        help="Parent Model: mv.discount",
    )
    warranty_discount_policy_id = fields.Many2one(
        "mv.warranty.discount.policy",
        "Chính sách chiết khấu kích hoạt",
        domain=[("active", "=", True)],
        help="Parent Model: mv.warranty.discount.policy",
    )
    partner_id = fields.Many2one(
        "res.partner",
        "Khách hàng / Đại lý",
        domain=[("is_agency", "=", True)],
        help="Parent Model: res.partner",
    )
    partner_agency = fields.Boolean(help="Make sure this is an agency")
    partner_white_agency = fields.Boolean(help="Make sure this is a white agency")
    needs_update = fields.Boolean(
        default=False, help="Warning: This record needs to be updated"
    )

    _sql_constraints = [
        (
            "parent_id_warranty_discount_policy_id_partner_id_unique",
            "unique (parent_id, warranty_discount_policy_id, partner_id)",
            "This Customer/Dealer has a registered Discount Policy, please check again.",
        ),
    ]

    # =================================
    # ACTION Methods
    # =================================

    def action_update_partner_discount(self):
        self.ensure_one()
        return {
            "name": _(f"Cập nhật chính sách {self.parent_id.name}"),
            "type": "ir.actions.act_window",
            "res_model": "mv.wizard.update.partner.discount",
            "view_mode": "form",
            "view_id": self.env.ref(
                "mv_sale.mv_wizard_update_partner_discount_form_view"
            ).id,
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_date_effective": self.date,
                "default_level": self.level,
                "default_min_debt": self.min_debt,
                "default_max_debt": self.max_debt,
                "default_number_debt": self.number_debt,
                "create": False,
                "edit": False,
            },
            "target": "new",
        }
