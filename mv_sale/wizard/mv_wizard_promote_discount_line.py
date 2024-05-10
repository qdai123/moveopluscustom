# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models


class MVWizardPromoteDiscountLine(models.TransientModel):
    _name = _description = "mv.wizard.promote.discount.line"

    compute_discount_id = fields.Many2one("mv.compute.discount", readonly=True)
    compute_discount_line_id = fields.Many2one(
        "mv.compute.discount.line", readonly=True
    )
    partner_id = fields.Many2one("res.partner", readonly=True)
    promote_discount = fields.Many2one(
        "mv.promote.discount.line", context={"wizard_promote_discount_search": True}
    )
    promote_discount_percentage = fields.Float("% Promote Discount")

    @api.onchange("promote_discount")
    def _onchange_promote_discount_percentage(self):
        if self.promote_discount:
            self.promote_discount_percentage = (
                self.promote_discount.promote_discount / 100
            )

    def action_save(self):
        vals = {}
        amount = 0
        compute_discount = False
        discount_env = self.env["mv.compute.discount"]
        discount_line = False
        discount_line_env = self.env["mv.compute.discount.line"]
        if self.compute_discount_line_id:
            discount_line = discount_line_env.browse(self.compute_discount_line_id.id)

        if self.compute_discount_id:
            compute_discount = discount_env.browse(self.compute_discount_id.id)

        if compute_discount and discount_line:
            promote_discount_percentage = (
                self.promote_discount_percentage
                or self.promote_discount.promote_discount / 100
            )
            vals.update(
                {
                    "partner_sales_state": "qualified_by_approving",
                    "is_promote_discount": True,
                    "promote_discount_percentage": self.promote_discount_percentage,
                    "promote_discount_money": discount_line.amount_total
                    * promote_discount_percentage,
                }
            )
            discount_line.write(vals)

            # Tracking value
            tracking_text = """
                <div class="o_mail_notification">
                    %s đã xác nhận chiết khấu khuyến khích cho %s. <br/>
                    Với số tiền là: <b>%s</b>
                </div>
            """
            compute_discount.message_post(
                body=Markup(tracking_text)
                % (
                    self.env.user.name,
                    self.partner_id.name,
                    discount_line.format_value(
                        amount=discount_line.promote_discount_money,
                        currency=discount_line.currency_id,
                    ),
                )
            )
