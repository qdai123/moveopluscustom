# -*- coding: utf-8 -*-

from odoo import models, api, fields

def get_years():
    year_list = []
    for i in range(2023, 2036):
        year_list.append((str(i), str(i)))
    return year_list


class DiscountReport(models.Model):
    _name = 'discount.report'

    line_ids = fields.One2many("discount.report.line", "parent_id")
    partner_id = fields.Many2one("res.partner", required=1, string="Đại lý")
    name = fields.Selection(get_years(), string='Năm', required=1)

    def create_discount_report(self, description, january, february, march, april, may, june, july, august, september,
                               october, november, december):
        self.env['discount.report.line'].create({
            'parent_id': self.id,
            'partner_id': self.partner_id.id,
            'description': description,
            'january' : january,
            'february': february,
            'march': march,
            'april': april,
            'may': may,
            'june': june,
            'july': july,
            'august': august,
            'september': september,
            'october': october,
            'november': november,
            'december': december,
        })
        
    def convert_vnd(self, amount):
        a = format(amount, ',.0f')
        return a
    def action_confirm(self):
        self.line_ids = False
        compute_discount_ids = self.env['mv.compute.discount'].search([('year', '=', self.name)])
        compute_discount_line_ids = compute_discount_ids.line_ids.filtered(lambda x: x.partner_id == self.partner_id)
        self.create_discount_report("Tổng số lốp đặt hàng",
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('quantity'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('quantity'))))
        self.create_discount_report("Tổng giá trị đơn hàng trước VAT",
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('amount_total'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('amount_total'))))
        self.create_discount_report("Chiết khấu tháng",
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('month'))))
        self.create_discount_report("Số tiền chiết khấu",
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('month_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('month_money'))))
        self.create_discount_report("Chiết khấu 2 tháng",
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('two_month'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('two_month'))))
        self.create_discount_report("Số tiền chiết khấu",
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('two_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('two_money'))))
        self.create_discount_report("Chiết khấu quý",
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('quarter'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('quarter'))))
        self.create_discount_report("Số tiền chiết khấu",
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('quarter_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('quarter_money'))))
        self.create_discount_report("Chiết khấu năm ",
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('year'))),
                                    str(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('year'))))
        self.create_discount_report("Số tiền chiết khấu",
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('year_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('year_money'))))
        self.create_discount_report("Tổng chiết khấu",
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 1).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 2).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 3).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 4).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 5).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 6).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 7).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 8).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 9).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 10).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 11).mapped('total_money'))),
                                    self.convert_vnd(sum(compute_discount_line_ids.filtered(lambda x: x.month_parent == 12).mapped('total_money'))))
