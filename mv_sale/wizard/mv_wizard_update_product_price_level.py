# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, fields, models
from odoo.exceptions import UserError


def create_tracking_item(field_name, old_value, new_value):
    return f"""
    <li>
        <div class="o_Message_trackingValue">
            <div class="o_Message_trackingValueFieldName o_Message_trackingValueItem">
                {field_name}: {old_value} <i class="fa fa-long-arrow-right" role="img"/> {new_value}
            </div>
        </div>
    </li>
    """


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
    old_total_price_level_1 = fields.Float("Mức 1")
    new_total_price_level_1 = fields.Float("Mức 1")
    old_total_price_level_2 = fields.Float("Mức 2")
    new_total_price_level_2 = fields.Float("Mức 2")
    old_total_price_level_3 = fields.Float("Mức 3")
    new_total_price_level_3 = fields.Float("Mức 3")
    old_total_price_level_4 = fields.Float("Mức 4")
    new_total_price_level_4 = fields.Float("Mức 4")
    old_total_price_level_5 = fields.Float("Mức 5")
    new_total_price_level_5 = fields.Float("Mức 5")
    def action_update(self):
        self.ensure_one()
        self.check_prices()

        update_count = self.discount_product_level_line_id.update_count
        updated_values = self._prepare_updated_values(update_count)
        self.discount_product_level_line_id.write(updated_values)
        self.discount_policy_line_id._compute_total_price_discount()

        vals_log = self._generate_vals_log()
        tracking_text = self.generate_tracking_message(update_count + 1, vals_log)
        return self.discount_policy_line_id.parent_id.message_post(
            body=Markup(tracking_text)
        )

    def check_prices(self):
        if any(
            price < 0
            for price in [
                self.new_total_price_level_1,
                self.new_total_price_level_2,
                self.new_total_price_level_3,
                self.new_total_price_level_4,
                self.new_total_price_level_5,
            ]
        ):
            raise UserError(_("Price must be greater than 0."))

    def _prepare_updated_values(self, update_count):
        return {
            "total_price_level_1": self.new_total_price_level_1,
            "total_price_level_2": self.new_total_price_level_2,
            "total_price_level_3": self.new_total_price_level_3,
            "total_price_level_4": self.new_total_price_level_4,
            "total_price_level_5": self.new_total_price_level_5,
            "update_count": update_count + 1,
        }

    def _generate_vals_log(self):
        vals_log = []
        for level in range(1, 5):
            old_price = getattr(self, f"old_total_price_level_{level}")
            new_price = getattr(self, f"new_total_price_level_{level}")
            if old_price != new_price:
                vals_log.append((f"Price Level {level}", old_price, new_price))
                break
        return vals_log

    def generate_tracking_message(self, update_count, logs):
        user_name = self.env.user.name
        partner_name = self.discount_policy_line_id.partner_id.name

        tracking_update = (
            "%s đã điều chỉnh mức giá cho <strong>%s</strong>. [Lần thứ: %s]"
            % (user_name, partner_name, update_count)
        )
        tracking_update += (
            """<div class="o_Message_content"><ul class="o_Message_trackingValues">"""
        )

        for log in logs:
            field_update, old_value, new_value = log[0], log[1], log[2]
            tracking_update += create_tracking_item(field_update, old_value, new_value)

        tracking_update += """</ul></div>"""
        return tracking_update
