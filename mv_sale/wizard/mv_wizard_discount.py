# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class MvWizardDiscount(models.TransientModel):
    _name = _description = "mv.wizard.discount"

    order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    currency_id = fields.Many2one("res.currency", related="order_id.currency_id")
    currency_symbol = fields.Char(related="currency_id.symbol")
    company_id = fields.Many2one("res.company", related="order_id.company_id")
    partner_id = fields.Many2one(
        "res.partner", related="order_id.partner_id", required=True
    )
    amount = fields.Float(digits="Product Price")
    amount_partner = fields.Float(digits="Product Price")
    bonus_max = fields.Float(related="order_id.bonus_max", digits="Product Price")
    bonus_order = fields.Float(related="order_id.bonus_order", digits="Product Price")
    bonus_remaining = fields.Float(digits="Product Price")

    def action_confirm(self):
        try:
            if self.amount + self.bonus_order > self.bonus_max:
                raise UserError(
                    "Tổng tiền chiết khấu không được lớn hơn Số tiền chiết khấu tối đa."
                )
        except UserError as e:
            _logger.error("Error: %s", e)
            raise

        try:
            so = self.env["sale.order"].sudo().browse(self.order_id.id)
            return so.with_context(
                apply_partner_discount=True
            ).compute_discount_for_partner(bonus=self.amount)
        except Exception as e:
            _logger.error("Unexpected error: %s", e)
            raise UserError(_("An unexpected error occurred. Please try again."))
