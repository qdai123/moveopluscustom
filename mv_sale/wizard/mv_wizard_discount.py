# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MvWizardDiscount(models.TransientModel):
    _name = _description = "mv.wizard.discount"

    currency_id = fields.Many2one("res.currency", readonly=True)
    currency_symbol = fields.Char(compute="_compute_currency_symbol")
    sale_id = fields.Many2one("sale.order", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    amount = fields.Float("Số tiền sẽ chiết khấu", digits="Product Price")
    amount_partner = fields.Integer(
        "Số tiền chiết khấu hiện có",
        related="partner_id.amount",
        digits="Product Price",
    )
    bonus_max = fields.Float(
        "Số tiền có thể chiết khấu tối đa",
        related="sale_id.bonus_max",
        digits="Product Price",
    )
    bonus_order = fields.Float(
        "Số tiền đã chiết khấu",
        related="sale_id.bonus_order",
        digits="Product Price",
    )

    @api.depends("currency_id")
    def _compute_currency_symbol(self):
        for record in self:
            symbol = "{symbol}".format(symbol=record.currency_id.symbol or "")
            record.currency_symbol = symbol

    def action_confirm(self):
        sale_order = self.env["sale.order"].sudo().browse(self.sale_id.id)
        return sale_order.with_context(
            wizard_compute_discount=True
        ).compute_discount_for_partner(bonus=self.amount)
