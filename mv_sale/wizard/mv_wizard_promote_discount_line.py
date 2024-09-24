# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, api, fields, models


class MVWizardPromoteDiscountLine(models.TransientModel):
    _name = "mv.wizard.promote.discount.line"
    _description = _("MO+ Wizard Promote Discount Line")

    compute_discount_id = fields.Many2one("mv.compute.discount", readonly=True)
    compute_discount_line_id = fields.Many2one(
        "mv.compute.discount.line", readonly=True
    )
    partner_id = fields.Many2one("res.partner", readonly=True)
    promote_discount = fields.Many2one(
        "mv.promote.discount.line",
        domain=[("parent_id", "!=", False)],
        context={"wizard_promote_discount_search": True},
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
        compute_discount = False
        discount_line = False
        discount_env = self.env["mv.compute.discount"]
        discount_line_env = self.env["mv.compute.discount.line"]
        if self.compute_discount_line_id:
            discount_line = discount_line_env.browse(self.compute_discount_line_id.id)

        if self.compute_discount_id:
            compute_discount = discount_env.browse(self.compute_discount_id.id)

        if compute_discount and discount_line:
            promote_discount = self.promote_discount.promote_discount
            promote_discount_percentage = (
                self.promote_discount_percentage or promote_discount / 100
            )
            total_money_promote_discount = (
                discount_line.amount_total * promote_discount_percentage
            )
            vals.update(
                {
                    "partner_sales_state": "qualified_by_approving",
                    "is_promote_discount": True,
                    "promote_discount_percentage": promote_discount,
                    "promote_discount_money": total_money_promote_discount,
                }
            )
            discount_line.write(vals)
            # Create history line for discount
            total_money_promote_discount = (
                discount_line.amount_total * promote_discount_percentage
            )
            is_positive_money = total_money_promote_discount > 0
            description = (
                "Đã duyệt Chiết Khấu Khuyến Khích cho đại lý, đang chờ duyệt tổng tháng %s."
                % discount_line.name
            )
            self.env["mv.discount.partner.history"]._create_history_line(
                partner_id=discount_line.partner_id.id,
                history_description=description,
                production_discount_policy_id=discount_line.id,
                production_discount_policy_total_money=total_money_promote_discount,
                total_money=total_money_promote_discount,
                total_money_discount_display=(
                    "+ {:,.2f}".format(total_money_promote_discount)
                    if total_money_promote_discount > 0
                    else "{:,.2f}".format(total_money_promote_discount)
                ),
                is_waiting_approval=False,
                is_positive_money=is_positive_money,
                is_negative_money=False,
            )
            # Tracking for user
            compute_discount.message_post(
                body=Markup(
                    """
                    <div class="o_mail_notification">
                        %s đã xác nhận chiết khấu khuyến khích cho %s. <br/>
                        Với số tiền là: <b>%s</b>
                    </div>
                """
                )
                % (
                    self.env.user.name,
                    self.partner_id.name,
                    discount_line.format_value(
                        amount=discount_line.promote_discount_money,
                        currency=discount_line.currency_id,
                    ),
                )
            )
