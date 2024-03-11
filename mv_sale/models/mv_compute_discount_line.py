# -*- coding: utf-8 -*-

from odoo import models, api, fields


class MvComputeDiscountLine(models.Model):
    _name = 'mv.compute.discount.line'

    parent_id = fields.Many2one("mv.compute.discount")
    partner_id = fields.Many2one("res.partner", string="Partner")
    level = fields.Integer(string="Level")
    quantity = fields.Integer(string="Quantity")
    amount_total = fields.Float(string="Amount of month")
    quantity_from = fields.Integer(string="Quantity From")
    quantity_to = fields.Integer(string="Quanity To")
    basic = fields.Float(string="Basic")
    is_month = fields.Boolean()
    month = fields.Float(string="Month")
    month_money = fields.Integer(string="Money")
    is_two_month = fields.Boolean()
    two_month = fields.Float(string="Two Month")
    two_money = fields.Integer(string="Money")
    is_quarter = fields.Boolean()
    quarter = fields.Float(string="Quarter")
    quarter_money = fields.Integer(string="Money")
    is_year = fields.Boolean()
    year = fields.Float(string="Year")
    year_money = fields.Integer(string="Money")
    total_discount = fields.Float(string="Total % discount")
    total_money = fields.Integer(string="Total money discount")
    sale_ids = fields.One2many("sale.order", "discount_line_id")
    order_line_ids = fields.One2many("sale.order.line", "discount_line_id")
    currency_id = fields.Many2one('res.currency')
