# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import fields, models, _


class MVWizardUpdatePartnerDiscount(models.TransientModel):
    _name = _description = "mv.wizard.update.partner.discount"

    partner_id = fields.Many2one("res.partner", readonly=True)
    date_effective = fields.Date("Date Effective")
    level = fields.Integer("Level", default=0)
    min_debt = fields.Integer("Min Debt", default=0)
    max_debt = fields.Integer("Max Debt", default=0)
    number_debt = fields.Float("Ratio Debt", default=0)

    def action_update(self):
        self.ensure_one()
        self.env["mv.discount.partner"].search(
            [("partner_id", "=", self.partner_id.id)], limit=1
        ).write(
            {
                "date": self.date_effective,
                "level": self.level,
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
