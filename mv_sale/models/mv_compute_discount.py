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

    name = fields.Char(string="Name", compute="compute_name")
    date = fields.Date("Month")
    line_ids = fields.One2many("mv.compute.discount.line", "parent_id")
    month = fields.Selection([('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'),
                              ('5', '5'), ('6', '6'), ('7', '7'), ('8', '8'),
                              ('9', '9'), ('10', '10'), ('11', '11'), ('12', '12')],
                             string='Tháng')
    year = fields.Selection(get_years(), string='Year')
    state = fields.Selection(
        [('draft', 'New'), ('confirm', 'Confirm'), ('done', 'Done'), ], 'State', default="draft")

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

        # domain lọc dữ liệu sale
        domain = [('date_order', '>=', date_from), ('date_order', '<=', date_to), ('state', 'in', ['sale'])]
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

            # xác định số lượng đại lý trong tháng
            order_line_partner = order_line.filtered(lambda x: x.order_id.partner_id == partner_id)
            quantity = sum(order_line_partner.mapped('product_uom_qty'))
            # xác định cấp bậc đại lý
            line_ids = partner_id.line_ids.filtered(lambda x: date.today() >= x.date if x.date else not x.date).sorted('level')
            if len(line_ids) > 0:
                level = line_ids[-1].level
                print(level)
                discount_id = line_ids[-1].parent_id
                print(discount_id)
                discount_line_id = discount_id.line_ids.filtered(lambda x: x.level == level)
                if quantity >= discount_line_id.quantity_from:
                    # đạt được chỉ tiêu tháng
                    is_month = True
                    amount_total = sum(order_line_partner.order_id.mapped('amount_total'))
                    month_money = amount_total * discount_line_id.month / 100
                    print(month_money)
            if discount_line_id.level:
                value = ((0, 0, {
                    'partner_id': partner_id.id,
                    'level': discount_line_id.level,
                    'quantity': quantity,
                    'quantity_from': discount_line_id.quantity_from,
                    'quantity_to': discount_line_id.quantity_to,
                    'amount_total': amount_total,
                    'is_month': is_month,
                    'month': discount_line_id.month,
                    'month_money': month_money,
                    'sale_ids': order_line_partner.order_id.ids,
                    'order_line_ids': order_line_partner.ids,
                    'currency_id': order_line_partner[0].order_id.currency_id.id,
                }))
                list_line_ids.append(value)
        self.line_ids = list_line_ids


    def action_done(self):
        print("aloaoalalaoa")

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
