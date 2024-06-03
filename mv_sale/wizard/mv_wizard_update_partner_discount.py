# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import fields, models, _
from odoo.exceptions import UserError


class MVWizardUpdatePartnerDiscount(models.TransientModel):
    _name = _description = "mv.wizard.update.partner.discount"

    partner_id = fields.Many2one("res.partner", readonly=True)
    discount_id = fields.Many2one("mv.discount", readonly=True)
    warranty_discount_policy_id = fields.Many2one(
        "mv.warranty.discount.policy", readonly=True
    )
    date_effective = fields.Date("Date Effective")
    current_level = fields.Integer("Old Level", readonly=True)
    new_level = fields.Integer("Level")
    min_debt = fields.Integer("Min Debt")
    max_debt = fields.Integer("Max Debt")
    number_debt = fields.Float("Ratio Debt")

    def action_update(self):
        self.ensure_one()

        if (
            self.partner_id.is_white_agency
            and self.current_level == 0
            and self.new_level > self.current_level
        ):
            raise UserError(
                _(
                    "Vui lòng bỏ 'tick' ở Đại lý Vùng Trắng để cập nhật lại Cấp bậc cho Đại lý này!"
                )
            )

        # Update partner discount
        self.env["mv.discount.partner"].search(
            [("partner_id", "=", self.partner_id.id)], limit=1
        ).write(
            {
                "date": self.date_effective,
                "level": self.new_level,
                "min_debt": self.min_debt,
                "max_debt": self.max_debt,
                "number_debt": self.number_debt,
                "needs_update": False,
            }
        )

        # Tracking value
        tracking_text = """
            <div class="o_mail_notification">
                %s đã cập nhật chính sách cho %s.
            </div>
        """
        self.partner_id.message_post(
            body=Markup(tracking_text) % (self.env.user.name, self.partner_id.name)
        )
