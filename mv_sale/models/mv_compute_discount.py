# -*- coding: utf-8 -*-

from odoo import models, api, fields
from datetime import datetime, timedelta, date


def get_years():
    year_list = []
    for i in range(2023, 2036):
        year_list.append((str(i), str(i)))
    return year_list


class MvComputeDiscount(models.Model):
    _name = 'mv.compute.discount'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Compute discount for partner"

    name = fields.Char(string="Name", compute="compute_name")
    date = fields.Date("Month")
    line_ids = fields.One2many("mv.compute.discount.line", "parent_id")
    month = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'),
                              ('5', '5'), ('6', '6'), ('7', '7'), ('8', '8'),
                              ('9', '9'), ('10', '10'), ('11', '11'), ('12', '12')],
                             string='Tháng')
    year = fields.Selection(get_years(), string='Year')
    state = fields.Selection(
        [('draft', 'Nháp'), ('confirm', 'Lưu'), ('done', 'Đã Duyệt'), ], 'State', default="draft")

    _sql_constraints = [
        ('month_year_uniq', 'unique (month, year)',
         "Tháng và năm này đã tồn tại không được tạo nữa")
    ]

    @api.depends('month', 'year')
    def compute_name(self):
        for record in self:
            record.name = str(record.month) + '/' + str(record.year)

    def action_confirm(self):
        self.line_ids = False
        list_line_ids = []
        # compute date
        date_from = '01-' + self.month + '-' + self.year
        date_from = datetime.strptime(date_from, "%d-%m-%Y")
        if self.month == '12':
            date_to = '31-' + self.month + '-' + self.year
        else:
            date_to = '01-' + str(int(self.month) + 1) + '-' + self.year
        date_to = datetime.strptime(date_to, "%d-%m-%Y") - timedelta(days=1)

        # domain lọc dữ liệu sale trong tháng
        domain = [('date_invoice', '>=', date_from), ('date_invoice', '<=', date_to), ('state', 'in', ['sale'])]
        sale_ids = self.env['sale.order'].search(domain)

        # lấy tất cả đơn hàng trong tháng, có mua lốp xe có category 19
        order_line = sale_ids.order_line.filtered(lambda x: x.order_id.partner_id.is_agency
            and x.product_id.detailed_type == 'product' and x.order_id.check_category_product(x.product_id.categ_id))

        # lấy tất cả đại lý trong tháng
        partner_ids = order_line.order_id.mapped('partner_id')
        for partner_id in partner_ids:
            # giá trị ban đầu:
            discount_line_id = False
            amount_total = False
            is_month = False
            month_money = 0
            is_two_month = False
            amount_two_month = 0
            two_month = 0
            two_money = 0
            is_quarter = False
            quarter = 0
            quarter_money = 0
            is_year = False
            year = 0
            year_money = 0


            # xác định số lượng đại lý trong tháng
            order_line_total = order_line.filtered(lambda x: x.order_id.partner_id == partner_id)
            order_line_partner = order_line_total.filtered(lambda x: x.order_id.partner_id == partner_id and x.price_unit > 0)
            quantity = sum(order_line_partner.mapped('product_uom_qty'))
            # xác định số lương đơn hàng có giá = 0, hàng khuyến mãi
            order_line_partner_discount = order_line_total.filtered(lambda x: x.order_id.partner_id == partner_id and x.price_unit == 0)
            quantity_discount = sum(order_line_partner_discount.mapped('product_uom_qty'))
            # xác định cấp bậc đại lý
            line_ids = partner_id.line_ids.filtered(lambda x: date.today() >= x.date if x.date else not x.date).sorted('level')
            if len(line_ids) > 0:
                level = line_ids[-1].level
                discount_id = line_ids[-1].parent_id
                discount_line_id = discount_id.line_ids.filtered(lambda x: x.level == level)
                amount_total = sum(order_line_partner.mapped('price_subtotal'))
                if quantity >= discount_line_id.quantity_from:
                    # đạt được chỉ tiêu tháng 1 chỉ cần thỏa số lượng trong tháng
                    is_month = True
                    month_money = amount_total * discount_line_id.month / 100
                    # để đạt kết quả 2 tháng:
                    # 1- tháng này phải đạt chỉ tiêu tháng
                    # 2 - tháng trước phải đạt chỉ tiêu tháng và chưa đạt chỉ tiêu 2 tháng
                    if self.month == '1':
                        name = '12' + '/' + str(int(self.year) - 1)
                    else:
                        name = str(int(self.month) - 1) + '/' + self.year
                    domain = [('name', '=', name), ('is_month', '=', True), ('is_two_month', '=', False), ('partner_id', '=', partner_id.id)]
                    line_two_month_id = self.env['mv.compute.discount.line'].search(domain)
                    if len(line_two_month_id) > 0:
                        is_two_month = True
                        two_month = discount_line_id.two_month
                        amount_two_month = line_two_month_id.amount_total + amount_total
                        two_money = amount_two_month * discount_line_id.two_month / 100
                    # để đạt kết quả quý [1, 2, 3] [4, 5, 6] [7, 8, 9] [10, 11, 12]:
                    # chỉ xét quý vào các tháng 3 6 9 12, chỉ cần kiểm tra 2 tháng trước đó có đạt chỉ tiêu tháng ko
                    if self.month in ['3', '6', '9', '12']:
                        name_one = str(int(self.month) - 1) + '/' + self.year
                        name_two = str(int(self.month) - 2) + '/' + self.year
                        domainone = [('name', '=', name_one), ('is_month', '=', True), ('partner_id', '=', partner_id.id)]
                        line_name_one = self.env['mv.compute.discount.line'].search(domainone)
                        domain_two = [('name', '=', name_two), ('is_month', '=', True), ('partner_id', '=', partner_id.id)]
                        line_name_two = self.env['mv.compute.discount.line'].search(domain_two)
                        if len(line_name_one) >= 1 and len(line_name_two) >= 1:
                            is_quarter = True
                            quarter = discount_line_id.quarter
                            quarter_money = (amount_total + line_name_one.amount_total + line_name_two.amount_total) * discount_line_id.two_month / 100
                    # để đạt kết quả năm thì tháng đang xet phai la 12
                    # kiểm tra 11 tháng trước đó đã được chỉ tiêu tháng chưa
                    if self.month in ['12']:
                        flag = True
                        total_year = 0
                        for i in range(12):
                            print(i)
                            name = str(i + 1) + '/' + self.year
                            domain = [('name', '=', name), ('is_month', '=', True), ('partner_id', '=', partner_id.id)]
                            line_name = self.env['mv.compute.discount.line'].search(domain)
                            if len(line_name) == 0:
                                flag = False
                            total_year += line_name.amount_total
                        if flag:
                            is_year = True
                            year = discount_line_id.quarter
                            year_money = total_year * discount_line_id.year / 100

                    print(month_money)
            if discount_line_id.level:
                value = ((0, 0, {
                    # tính dữ liệu tháng này
                    'discount_line_id': discount_line_id.id,
                    'month_parent': int(self.month),
                    'partner_id': partner_id.id,
                    'level': discount_line_id.level,
                    'sale_ids': order_line_total.order_id.ids,
                    'order_line_ids': order_line_total.ids,
                    'currency_id': order_line_total[0].order_id.currency_id.id,
                    'quantity': quantity,
                    'quantity_discount': quantity_discount,
                    'quantity_from': discount_line_id.quantity_from,
                    'quantity_to': discount_line_id.quantity_to,
                    'amount_total': amount_total,
                    'is_month': is_month,
                    'month': discount_line_id.month,
                    'month_money': month_money,
                    # tính 2 tháng
                    'is_two_month': is_two_month,
                    'amount_two_month': amount_two_month,
                    'two_month': two_month,
                    'two_money': two_money,
                    # tính theo quý
                    'is_quarter': is_quarter,
                    'quarter': quarter,
                    'quarter_money': quarter_money,
                    # tính theo năm
                    'is_year': is_year,
                    'year': year,
                    'year_money': year_money,
                }))
                list_line_ids.append(value)
        self.write({
            'line_ids': list_line_ids,
            'state': 'confirm',
        })


    def action_done(self):
        for line in self.line_ids:
            line.partner_id.write({
                'amount': line.partner_id.amount + line.total_money
            })
        self.write({
            'state': 'done'
        })

    def action_view_tree(self):
        return {
            'name': "Kết quả chiết khấu của tháng: %s" %(self.name),
            'view_mode': 'tree,form',
            'res_model': 'mv.compute.discount.line',
            'type': 'ir.actions.act_window',
            'domain': [('parent_id', '=', self.id)],
            'context': {
                'create': False,
                'edit': False,
                'tree_view_ref': 'mv_sale.mv_compute_discount_line_tree',
                'form_view_ref': 'mv_sale.mv_compute_discount_line_form',
            }
        }

    def action_undo(self):
        self.write({
            'state': 'draft',
            'line_ids': False,
        })
