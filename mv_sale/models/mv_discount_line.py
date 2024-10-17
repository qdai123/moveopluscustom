# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MvDiscountPolicyLine(models.Model):
    _name = _description = "mv.discount.line"

    parent_id = fields.Many2one("mv.discount")
    level = fields.Integer("Bậc")
    pricelist_id = fields.Many2one("product.pricelist", "Chính sách giá")
    quantity_from = fields.Integer("Số lượng min")
    quantity_to = fields.Integer("Số lượng max")
    basic = fields.Float("Ck cơ bản")
    money = fields.Integer("Money")
    month = fields.Float("Ck tháng")
    month_money = fields.Integer("Money")
    two_month = fields.Float("Ck 2 tháng")
    two_money = fields.Integer("Money")
    quarter = fields.Float("Ck quý")
    quarter_money = fields.Integer("Money")
    year = fields.Float("Ck năm")
    year_money = fields.Integer("Money")
    total_discount = fields.Float("Total % discount")
    total_money = fields.Integer("Total money discount")
    average = fields.Float("Average by month")
    min_debt = fields.Integer("Min debt")
    max_debt = fields.Integer("Max debt")
    number_debt = fields.Float("Ratio Debt")
    discount_payment = fields.Float("Discount for on-time payment")
    discount_guarantee = fields.Float("Guarantee opening discount")
    total_all = fields.Float("Total discount")

    @api.onchange("pricelist_id")
    def onchange_pricelist(self):
        self.basic = 0
        self._update_basic_discount()

    def _update_basic_discount(self):
        """Updates the basic discount based on the pricelist."""
        if self.pricelist_id and self.pricelist_id.item_ids:
            item = self.pricelist_id.item_ids[0]
            if item.compute_price == "percentage":
                self.basic = item.percent_price
