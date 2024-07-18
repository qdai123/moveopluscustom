# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class MvDiscountPolicyPartner(models.Model):
    _name = _description = "mv.discount.partner"
    _rec_name = "partner_id"

    # === Model: [res.partner] Fields ===#
    partner_id = fields.Many2one(
        "res.partner", "Khách hàng / Đại lý", domain=[("is_agency", "=", True)]
    )
    partner_agency = fields.Boolean(compute="_compute_partner_agency")
    partner_white_agency = fields.Boolean(compute="_compute_partner_agency")
    partner_southern_agency = fields.Boolean(compute="_compute_partner_agency")
    # === Model: [mv.discount] Fields ===#
    parent_id = fields.Many2one(
        "mv.discount", "Chính sách chiết khấu", domain=[("active", "=", True)]
    )
    # === Model: [mv.warranty.discount.policy] Fields ===#
    warranty_discount_policy_ids = fields.Many2many(
        "mv.warranty.discount.policy",
        "mv_warranty_discount_policy_partner_rel",
        "mv_warranty_discount_policy_id",
        "mv_discount_partner_id",
        string="Chính sách chiết khấu kích hoạt",
        domain=[("active", "=", True)],
    )
    # === Other Fields ===#
    date = fields.Date(
        "Ngày hiệu lực", default=fields.Date.today().replace(day=1, month=1)
    )  # Default: 1/1/(Current Year)
    level = fields.Integer("Cấp bậc", default=0)
    min_debt = fields.Integer("Min Debt", default=0)
    max_debt = fields.Integer("Max Debt", default=0)
    number_debt = fields.Float("Ratio Debt", default=0)
    needs_update = fields.Boolean("Cần cập nhật", default=False)

    _sql_constraints = [
        (
            "parent_id_partner_id_unique",
            "unique (parent_id, partner_id)",
            "This Customer/Dealer has a registered Discount Policy, please check again.",
        ),
    ]

    @api.depends("partner_id")
    def _compute_partner_agency(self):
        for mv_partner in self:
            mv_partner.partner_agency = mv_parner.partner_id.is_agency or False
            mv_partner.partner_white_agency = (
                mv_parner.partner_id.is_white_agency or False
            )
            mv_partner.partner_southern_agency = (
                mv_parner.partner_id.is_southern_agency or False
            )

    # =================================
    # ORM / CRUD Methods
    # =================================

    def write(self, vals):
        res = super().write(vals)

        if res:
            for record in self:
                if (
                    record.parent_id
                    and record.partner_id
                    and record.warranty_discount_policy_ids
                ):
                    record.partner_id.write(
                        {
                            "warranty_discount_policy_ids": [
                                (6, 0, record.warranty_discount_policy_ids.ids)
                            ]
                        }
                    )

        return res

    # =================================
    # ACTION Methods
    # =================================

    def action_update_partner_discount(self):
        self.ensure_one()
        return {
            "name": _(f"Cập nhật chính sách cho {self.partner_id.name}"),
            "type": "ir.actions.act_window",
            "res_model": "mv.wizard.update.partner.discount",
            "view_mode": "form",
            "view_id": self.env.ref(
                "mv_sale.mv_wizard_update_partner_discount_form_view"
            ).id,
            "context": {
                "default_partner_id": self.partner_id.id,
                "default_date_effective": self.date,
                "default_current_level": self.level,
                "default_new_level": self.level,
                "default_min_debt": self.min_debt,
                "default_max_debt": self.max_debt,
                "default_number_debt": self.number_debt,
                "create": False,
                "edit": False,
            },
            "target": "new",
        }
