# -*- coding: utf-8 -*-

from odoo import models, api, fields


class MvComputeDiscountLine(models.Model):
    _name = 'mv.compute.discount.line'

    name = fields.Char(related="parent_id.name", store=True)
    month_parent = fields.Integer()
    parent_id = fields.Many2one("mv.compute.discount")
    partner_id = fields.Many2one("res.partner", string="Partner")
    level = fields.Integer(string="Level")
    quantity = fields.Integer(string="Quantity")
    amount_total = fields.Float(string="Amount this month")
    quantity_from = fields.Integer(string="Quantity From")
    quantity_to = fields.Integer(string="Quanity To")
    basic = fields.Float(string="Basic")
    is_month = fields.Boolean()
    month = fields.Float(string="Month")
    month_money = fields.Integer(string="Money one month")
    is_two_month = fields.Boolean()
    amount_two_month = fields.Float(string="Amount two month")
    two_month = fields.Float(string="Two month")
    two_money = fields.Integer(string="Money two month")
    is_quarter = fields.Boolean()
    quarter = fields.Float(string="Quarter")
    quarter_money = fields.Integer(string="Money quarter")
    is_year = fields.Boolean()
    year = fields.Float(string="Year")
    year_money = fields.Integer(string="Money year")
    total_discount = fields.Float(string="Total % discount")
    total_money = fields.Integer(string="Total money", compute="compute_total_money", store=True)
    sale_ids = fields.One2many("sale.order", "discount_line_id")
    order_line_ids = fields.One2many("sale.order.line", "discount_line_id")
    currency_id = fields.Many2one('res.currency')
    discount_line_id = fields.Many2one("mv.discount.line")

    @api.depends('month_money', 'two_money', 'quarter_money', 'year_money')
    def compute_total_money(self):
        for record in self:
            record.total_money = record.month_money + record.two_money + record.quarter_money + record.year_money

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

    def action_view_year(self):
        year = self.parent_id.year
        list_name = ['1' + '/' + year, '2' + '/' + year, '3' + '/' + year, '4' + '/' + year, '5' + '/' + year,
                     '6' + '7' + year, '8' + '/' + year, '9' + '/' + year, '10' + '/' + year, '11' + '/' + year,
                     '12' + '/' + year]
        domain = [('partner_id', '=', self.partner_id.id),('name', '=', list_name)]
        line_ids = self.search(domain)
        return {
            'name': "Chiếu khấu theo theo năm %s" %(year),
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

    def action_quarter(self):
        amount_two_month = 0
        name_one = str(int(self.month_parent) - 1) + '/' + self.parent_id.year
        name_two = str(int(self.month_parent) - 2) + '/' + self.parent_id.year
        domain = [('name', 'in', [name_one, name_two]), ('partner_id', '=', self.partner_id.id)]
        line_ids = self.env['mv.compute.discount.line'].search(domain)
        if len(line_ids) > 0:
            for line in line_ids:
                amount_two_month += line.amount_total
        self.write({
            'is_quarter': True,
            'quarter': self.discount_line_id.quarter,
            'quarter_money': (amount_two_month + self.amount_total) * self.discount_line_id.quarter / 100
        })
        self.parent_id.message_post(body="%s đã xác nhận chiết khấu quý cho người dùng %s với số tiền là: %s" % (
        self.env.user.name, self.partner_id.name, str(self.quarter_money)))

    def action_year(self):
        total_year = 0
        for i in range(12):
            print(i)
            name = str(i + 1) + '/' + self.parent_id.year
            domain = [('name', '=', name), ('partner_id', '=', self.partner_id.id)]
            line_ids = self.env['mv.compute.discount.line'].search(domain)
            if len(line_ids) > 0:
                total_year += line_ids.amount_total
        self.write({
            'is_year': True,
            'year': self.discount_line_id.year,
            'year_money': total_year * self.discount_line_id.year / 100
        })
        self.parent_id.message_post(body="%s đã xác nhận chiết khấu năm cho người dùng %s với số tiền là: %s" % (self.env.user.name, self.partner_id.name, str(total_year)))
