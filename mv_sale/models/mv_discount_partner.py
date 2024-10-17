# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class MvDiscountPolicyPartner(models.Model):
    _name = _description = "mv.discount.partner"
    _rec_name = "partner_id"

    # === CHÍNH SÁCH: CHIẾT KHẤU SẢN LƯỢNG ===#
    parent_id = fields.Many2one(
        "mv.discount",
        "CS: Chiết Khấu Sản Lượng",
        domain=[("active", "=", True)],
    )
    # === CHÍNH SÁCH: CHIẾT KHẤU KÍCH HOẠT BẢO HÀNH ===#
    warranty_discount_policy_ids = fields.Many2many(
        "mv.warranty.discount.policy",
        "mv_warranty_discount_policy_partner_rel",
        "mv_warranty_discount_policy_id",
        "mv_discount_partner_id",
        "CS: Chiết Khấu Kích Hoạt Bảo Hành",
        domain=[("active", "=", True)],
    )
    # === CHÍNH SÁCH: CHIẾT KHẤU GIẢM GIÁ ===#
    discount_policy_ids = fields.Many2many(
        "mv.discount.policy",
        "mv_discount_policy_mv_partner_rel",
        "mv_discount_policy_id",
        "mv_discount_partner_id",
        "CS: Chiết Khấu Giảm Giá",
        domain=[("active", "=", True)],
    )

    # ===================================== #
    partner_id = fields.Many2one(
        "res.partner",
        domain=[("is_agency", "=", True)],
    )
    partner_agency = fields.Boolean(compute="_compute_partner_agency", store=True)
    partner_white_agency = fields.Boolean(compute="_compute_partner_agency", store=True)
    partner_southern_agency = fields.Boolean(
        compute="_compute_partner_agency", store=True
    )
    date = fields.Date(
        "Effective date",
        default=fields.Date.today().replace(day=1, month=1),
    )
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
        for record in self:
            self._set_agency_status(record)

    def _set_agency_status(self, record):
        record.partner_agency = record.partner_id.is_agency or False
        record.partner_white_agency = record.partner_id.is_white_agency or False
        record.partner_southern_agency = record.partner_id.is_southern_agency or False

    # =================================
    # ORM / CRUD Methods
    # =================================

    def write(self, vals):
        res = super().write(vals)
        if res:
            self.filtered(
                lambda rec: rec.parent_id
                and rec.partner_id
                and rec.warranty_discount_policy_ids
            ).mapped("partner_id").write(
                {
                    "warranty_discount_policy_ids": [
                        (6, 0, self.warranty_discount_policy_ids.ids)
                    ]
                }
            )
        return res

    # =================================
    # ACTION Methods
    # =================================

    def get_update_partner_discount_context(self):
        """Prepare and return the context for the wizard."""
        return {
            "default_partner_id": self.partner_id.id,
            "default_date_effective": self.date,
            "default_current_level": self.level,
            "default_new_level": self.level,
            "default_min_debt": self.min_debt,
            "default_max_debt": self.max_debt,
            "default_number_debt": self.number_debt,
            "create": False,
            "edit": False,
        }

    def action_update_partner_discount(self):
        self.ensure_one()

        # Return the action for opening the wizard form view
        return {
            "name": _("Update Policy for %s") % self.partner_id.name,
            "type": "ir.actions.act_window",
            "res_model": "mv.wizard.update.partner.discount",
            "view_mode": "form",
            "view_id": self.env.ref(
                "mv_sale.mv_wizard_update_partner_discount_form_view"
            ).id,
            "context": self.get_update_partner_discount_context(),
            "target": "new",
        }
