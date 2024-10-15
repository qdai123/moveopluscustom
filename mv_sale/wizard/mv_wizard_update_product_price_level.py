# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import UserError


class WizardUpdateProductPriceLevel(models.TransientModel):
    _name = _description = "mv.wizard.update.product.price.level"

    discount_policy_line_id = fields.Many2one(
        "mv.compute.discount.policy.line",
        readonly=True,
    )
    discount_product_level_line_id = fields.Many2one(
        "mv.compute.product.level.line",
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        readonly=True,
    )
    product_template_id = fields.Many2one(
        "product.template",
        readonly=True,
    )
    total_price_level_1 = fields.Float("Level 1")
    total_price_level_2 = fields.Float("Level 2")
    total_price_level_3 = fields.Float("Level 3")
    total_price_level_4 = fields.Float("Level 4")

    def action_update(self):
        self.ensure_one()
        self.check_prices()

        update_count = self.discount_product_level_line_id.update_count
        new_values = {
            "total_price_level_1": self.total_price_level_1,
            "total_price_level_2": self.total_price_level_2,
            "total_price_level_3": self.total_price_level_3,
            "total_price_level_4": self.total_price_level_4,
            "update_count": update_count + 1,
        }
        self.discount_product_level_line_id.write(new_values)
        self.discount_policy_line_id._compute_total_price_discount()

        tracking_text = self.generate_tracking_message(update_count + 1)
        self.discount_policy_line_id.parent_id.message_post(body=Markup(tracking_text))

    def check_prices(self):
        if any(
            price < 0
            for price in [
                self.total_price_level_1,
                self.total_price_level_2,
                self.total_price_level_3,
                self.total_price_level_4,
            ]
        ):
            raise UserError(_("Price must be greater than 0."))

    def generate_tracking_message(self, update_count):
        return """
        <div class="o_mail_notification">
            %s đã điều chỉnh mức giá cho %s. [Lần thứ: %s]
        </div>
        """ % (
            self.env.user.name,
            self.discount_policy_line_id.partner_id.name,
            update_count,
        )
