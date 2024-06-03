# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MvDiscountPolicyLine(models.Model):
    _name = "mv.discount.line"
    _description = _("MOVEO PLUS Discount Policy Line (%)")

    parent_id = fields.Many2one("mv.discount")
    level = fields.Integer(string="Bậc")
    pricelist_id = fields.Many2one("product.pricelist", string="Chính sách giá")
    quantity_from = fields.Integer(string="Số lượng min")
    quantity_to = fields.Integer(string="Số lượng max")
    basic = fields.Float(string="Ck cơ bản")
    money = fields.Integer(string="Money")
    month = fields.Float(string="Ck tháng")
    month_money = fields.Integer(string="Money")
    two_month = fields.Float(string="Ck 2 tháng")
    two_money = fields.Integer(string="Money")
    quarter = fields.Float(string="Ck quý")
    quarter_money = fields.Integer(string="Money")
    year = fields.Float(string="Ck năm")
    year_money = fields.Integer(string="Money")
    total_discount = fields.Float(string="Total % discount")
    total_money = fields.Integer(string="Total money discount")
    average = fields.Float(string="Average by month")
    min_debt = fields.Integer(string="Min debt")
    max_debt = fields.Integer(string="Max debt")
    number_debt = fields.Float(string="Ratio Debt")
    discount_payment = fields.Float(string="Discount for on-time payment")
    discount_guarantee = fields.Float(string="Guarantee opening discount")
    total_all = fields.Float(string="Total discount")

    @api.onchange("pricelist_id")
    def onchange_pricelist(self):
        self.basic = 0
        # thay đổi basic theo pricelist, quy tắc 1 pricelist chỉ được 1 rule
        if self.pricelist_id and len(self.pricelist_id.item_ids) > 0:
            item_id = self.pricelist_id.item_ids[0]
            if item_id.compute_price == "percentage":
                self.basic = item_id.percent_price
