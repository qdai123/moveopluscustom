# -*- coding: utf-8 -*-

from odoo import models, api, fields


class MvComputeDiscountLine(models.Model):
    _name = 'mv.compute.discount.line'

    name = fields.Char(related="parent_id.name", store=True)
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
    amount_two_month = fields.Float(string="Amount two month")
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

    def action_view_two_month(self):
        month = self.parent_id.month
        year = self.parent_id.year
        if month == '1':
            name_last = '12' + '/' + str(int(year) - 1)
        else:
            name_last = str(int(month) - 1) + '/' + year
        list_name = [self.name, name_last]
        domain = [('partner_id', '=', self.partner_id.id),('name', '=', list_name)]
        line_ids = self.search(domain)
        return {
            'name': "Chiếu khấu 2 tháng đạt chỉ tiêu",
            'view_mode': 'tree,form',
            'res_model': 'mv.compute.discount.line',
            'type': 'ir.actions.act_window',
            'domain': [('id', '=', line_ids.ids)],
            'context': {
                'create': False,
                'edit': False,
                'tree_view_ref': 'mv_sale.mv_compute_discount_line_tree',
                'form_view_ref': 'mv_sale.mv_compute_discount_line_form',
            }
        }

    def action_view_quarter(self):
        month = self.parent_id.month
        year = self.parent_id.year
        if month == '1':
            name_last = '12' + '/' + str(int(year) - 1)
        else:
            name_last = str(int(month) - 1) + '/' + year
        name_last_last = str(int(month) - 2) + '/' + year
        list_name = [self.name, name_last, name_last_last]
        domain = [('partner_id', '=', self.partner_id.id),('name', '=', list_name)]
        line_ids = self.search(domain)
        return {
            'name': "Chiếu khấu theo quý %s đạt chỉ tiêu" %str(int(month)/3),
            'view_mode': 'tree,form',
            'res_model': 'mv.compute.discount.line',
            'type': 'ir.actions.act_window',
            'domain': [('id', '=', line_ids.ids)],
            'context': {
                'create': False,
                'edit': False,
                'tree_view_ref': 'mv_sale.mv_compute_discount_line_tree',
                'form_view_ref': 'mv_sale.mv_compute_discount_line_form',
            }
        }
