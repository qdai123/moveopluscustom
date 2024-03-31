# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo import http


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    check_discount_10 = fields.Boolean(compute="_compute_check_discount_10", store=True, copy=False)
    total_price_no_service = fields.Float(compute="_compute_check_discount_10", help="Total price no include product service, no discount, no tax", store=True, copy=False)
    total_price_discount = fields.Float(compute="_compute_check_discount_10", help="Total price discount no include product service, no tax", store=True, copy=False)
    percentage = fields.Float(compute="_compute_check_discount_10", help="% discount of pricelist", store=True, copy=False)
    total_price_after_discount = fields.Float(compute="_compute_check_discount_10", help="Total price after discount no include product service, no tax", store=True, copy=False)
    bank_guarantee = fields.Boolean(string="Bảo lãnh ngân hàng", related="partner_id.bank_guarantee")
    discount_bank_guarantee = fields.Float(string="Bảo lãnh ngân hàng", compute="_compute_check_discount_10")
    after_discount_bank_guarantee = fields.Float(compute="_compute_check_discount_10",
                                                 help="Total price after discount bank guarantee", store=True,
                                                 copy=False)
    total_price_discount_10 = fields.Float(compute="_compute_check_discount_10", help="Total price discount 1% when product_uom_qty >= 10", store=True, copy=False)
    total_price_after_discount_10 = fields.Float(compute="_compute_check_discount_10", help="Total price after discount 1% when product_uom_qty >= 10", store=True, copy=False)
    # tổng số tiền tối đa mà khách hàng có thể áp dụng chiết khấu từ tài khoản bonus của mình
    bonus_max = fields.Float(compute="_compute_check_discount_10", help="Total price after discount 1% when product_uom_qty >= 10", store=True, copy=False)
    # tổng số tiền mà khách hàng đã áp dụng giảm chiết khấu
    bonus_order = fields.Float(copy=False)
    total_price_after_discount_month = fields.Float(compute="_compute_check_discount_10",
                                                 help="Total price after discount month",
                                                 store=True, copy=False)
    discount_line_id = fields.Many2one("mv.compute.discount.line")
    #  ngày hóa đơn xác nhận để làm căn cứ tính discount cho đại lý
    date_invoice = fields.Datetime(string="Date invoice", readonly=0)
    # giữ số lượng lại,để khi thay đổi thì xóa dòng delivery, chiết khấu tự đông, chiết khấu sản lượng
    quantity_change = fields.Float()
    flag_delivery = fields.Boolean(compute="compute_flag_delivery")

    # thuật toán kiếm cha là lốp xe
    def check_category_product(self, categ_id):
        if categ_id.id == 19:
            return True
        if categ_id.parent_id:
            return self.check_category_product(categ_id.parent_id)
        return False

    def check_show_warning(self):
        order_line = self.order_line.filtered(lambda x: x.product_id.detailed_type == 'product' and x.order_id.check_category_product(x.product_id.categ_id))
        if len(order_line) >= 1 and sum(order_line.mapped('product_uom_qty')) < 4:
            return True
        return False

    def compute_discount_for_partner(self, bonus):
        if bonus > self.bonus_max:
            return False
        else:
            if bonus > self.partner_id.amount:
                return bonus
            total_bonus = bonus + self.bonus_order
            if total_bonus > self.bonus_max:
                return total_bonus
            order_line_id = self.order_line.filtered(lambda x: x.product_id.default_code == 'CKT')
            if len(order_line_id) == 0:
                product_tmpl_id = self.env['product.template'].search([('default_code', '=', 'CKT')])
                if not product_tmpl_id:
                    product_tmpl_id = self.env['product.template'].create({
                        'name': 'Chiết khấu tháng',
                        'detailed_type': 'service',
                        'categ_id': 1,
                        'taxes_id': False,
                        'default_code': 'CKT'
                    })
                order_line_id = self.env['sale.order.line'].create({
                    'product_id': product_tmpl_id.product_variant_ids[0].id,
                    'order_id': self.id,
                    'product_uom_qty': 1,
                    'price_unit': 0,
                    'hidden_show_qty': True,
                    'code_product': 'CKT',
                })
            order_line_id.write({
                'price_unit': - total_bonus,
            })
            self.write({
                'bonus_order': total_bonus
            })
            self.partner_id.write({
                'amount': self.partner_id.amount - bonus
            })

    def create_discount_bank_guarantee(self):
        order_line = self.order_line.filtered(
            lambda x: x.product_id.detailed_type == 'product' and x.order_id.check_category_product(
                x.product_id.categ_id))
        if len(order_line) > 0:
            order_line_id = self.order_line.filtered(lambda x: x.code_product == 'CKBL')
            if len(order_line_id) == 0:
                product_tmpl_id = self.env['product.template'].search([('default_code', '=', 'CKBL')])
                if not product_tmpl_id:
                    product_tmpl_id = self.env['product.template'].create({
                        'name': 'Chiết khấu bảo lãnh',
                        'detailed_type': 'service',
                        'categ_id': 1,
                        'taxes_id': False,
                        'default_code': 'CKBL'
                    })
                url = http.request.httprequest.full_path
                if url.find('/shop/cart') > -1 or self._context.get('bank_guarantee', False):
                    order_line_id = self.env['sale.order.line'].create({
                        'product_id': product_tmpl_id.product_variant_ids[0].id,
                        'order_id': self.id,
                        'product_uom_qty': 1,
                        'price_unit': 0,
                        'hidden_show_qty': True,
                        'code_product': 'CKBL',
                    })
            if len(order_line_id) > 0:
                order_line_id.write({
                    'price_unit': - self.total_price_after_discount * self.partner_id.discount_bank_guarantee / 100,
                })


    @api.depends('order_line', 'order_line.product_uom_qty', 'order_line.product_id')
    def _compute_check_discount_10(self):
        for record in self:
            record.check_discount_10 = False
            record.total_price_no_service = 0
            record.total_price_discount = 0
            record.percentage = 0
            record.total_price_after_discount = 0
            record.total_price_discount_10 = 0
            record.total_price_after_discount_10 = 0
            record.after_discount_bank_guarantee = 0
            record.bonus_max = 0
            record.discount_bank_guarantee = 0
            record.total_price_after_discount_month = 0
            # kiểm tra xem thỏa điều kiện để mua đủ trên 10 lốp xe condinental
            if record.partner_id.is_agency and len(record.order_line) > 0:
                order_line = self.order_line.filtered(lambda x: x.product_id.detailed_type == 'product' and x.order_id.check_category_product(x.product_id.categ_id))
                if len(order_line) >= 1 and sum(order_line.mapped('product_uom_qty')) >= 10:
                    record.check_discount_10 = True
            # tính tổng tiền giá sản phầm không bao gồm hàng dịch vụ, tính giá gốc ban đầu, không bao gồm thuế phí
            if len(record.order_line) > 0:
                total_price_no_service = 0
                total_price_discount = 0
                percentage = 0
                for line in record.order_line.filtered(lambda x: x.product_id.detailed_type == 'product'):
                    total_price_no_service = total_price_no_service + line.price_unit * line.product_uom_qty
                    total_price_discount = total_price_discount + line.price_unit * line.product_uom_qty * line.discount / 100
                    percentage = line.discount
                record.total_price_no_service = total_price_no_service
                record.total_price_discount = total_price_discount
                record.percentage = percentage
                record.total_price_after_discount = record.total_price_no_service - record.total_price_discount
                if record.partner_id.bank_guarantee:
                    record.discount_bank_guarantee = record.total_price_after_discount * record.partner_id.discount_bank_guarantee / 100
                    if record.discount_bank_guarantee > 0:
                        record.create_discount_bank_guarantee()
                record.after_discount_bank_guarantee = record.total_price_after_discount - record.discount_bank_guarantee
                record.total_price_discount_10 = record.total_price_after_discount / 100
                record.total_price_after_discount_10 = record.after_discount_bank_guarantee  - record.total_price_discount_10
                record.total_price_after_discount_month = record.total_price_after_discount_10 - record.bonus_order
                record.bonus_max = (record.total_price_no_service - record.total_price_discount - record.total_price_discount_10 - record.discount_bank_guarantee) / 2
            # nếu đơn hàng không còn lốp xe nữa thì xóa chiết khấu tháng và chiết khấu bảo lãnh
            order_line_ctk = record.order_line.filtered(lambda x: x.product_id and x.product_id.default_code and x.product_id.default_code in ['CKT', 'CKBL'])
            order_line_product = record.order_line.filtered(lambda x: x.product_id.detailed_type == 'product')
            if len(order_line_ctk) > 0 and len(order_line_product) == 0:
                order_line_ctk.unlink()

    def action_cancel(self):
        if self.bonus_order > 0:
            self.partner_id.write({
                'amount': self.partner_id.amount + self.bonus_order
            })
            self.write({
                'bonus_order': 0
            })
        return super().action_cancel()

    def action_draft(self):
        order_line = self.order_line.filtered(lambda x: x.product_id.default_code == 'CKT')
        if len(order_line) > 0:
            bonus_order = order_line[0].price_unit
            self.partner_id.write({
                'amount': self.partner_id.amount + bonus_order
            })
            self.write({
                'bonus_order': -bonus_order
            })
        return super().action_draft()

    # hàm này để không tính thuế giao hàng
    def _get_reward_values_discount(self, reward, coupon, **kwargs):
        list = super()._get_reward_values_discount(reward, coupon, **kwargs)
        for line in list:
            b = {'tax_id': False}
            line.update(b)
        return list

    # hàm này xử lý số lượng trên thẻ cart, nó đang lấy luôn ca sản phẩm dịch vụ
    def _compute_cart_info(self):
        super(SaleOrder, self)._compute_cart_info()
        for order in self:
            service_lines = order.website_order_line.filtered(lambda line: line.product_id.detailed_type != 'product' and not line.is_reward_line)
            order.cart_quantity -= int(sum(service_lines.mapped('product_uom_qty')))

    def _get_order_lines_to_report(self):
        value = super()._get_order_lines_to_report()
        return value.sorted(key=lambda r: r.product_id.detailed_type)

    def action_compute_discount_month(self):
        if len(self.order_line) == 0:
            return
        self._update_programs_and_rewards()
        self._auto_apply_rewards()
        if self.partner_id.bank_guarantee:
            self.discount_bank_guarantee = self.total_price_after_discount * self.partner_id.discount_bank_guarantee / 100
            if self.discount_bank_guarantee > 0:
                self.with_context(bank_guarantee=True).create_discount_bank_guarantee()
        quantity_change = sum(self.order_line.filtered(lambda x: x.product_id.detailed_type == 'product').mapped('product_uom_qty'))
        ckt_order_line_id = self.order_line.filtered(lambda x: x.product_id.default_code == 'CKT')
        line_delivery_id = self.order_line.filtered(lambda x: x.is_delivery)
        len_line_delivery_id = len(line_delivery_id)
        # khi số lượng thay đổi thì xóa delivery, chiết khấu tháng
        if self.quantity_change != 0 and self.quantity_change != quantity_change:
            if len_line_delivery_id > 0:
                line_delivery_id.unlink()
                len_line_delivery_id = 0
            if len(ckt_order_line_id) > 0:
                ckt_order_line_id.unlink()
        self.write({
            'quantity_change': quantity_change
        })
        if len_line_delivery_id == 0:
            return self.action_open_delivery_wizard()
        view_id = self.env.ref('mv_sale.mv_wiard_discount_view_form').id
        if not self._context.get('confirm', False):
            return {
                'name': "Chiết khấu",
                'type': 'ir.actions.act_window',
                'view_mode': 'form',
                'res_model': 'mv.wizard.discount',
                'view_id': view_id,
                'views': [(view_id, 'form')],
                'target': 'new',
                'context': {
                    'default_sale_id': self.id,
                    'default_partner_id': self.partner_id.id,
                }
            }
    
    def action_confirm(self):
        if self.partner_id.is_agency:
            self.with_context(confirm=True).action_compute_discount_month()
            if len(self.order_line.filtered(lambda x: x.is_delivery)) == 0:
                return self.with_context(confirm=True).action_compute_discount_month()
        return super().action_confirm()

    def compute_flag_delivery(self):
        for record in self:
            record.flag_delivery = False
            if len(record.order_line) > 0 and len(self.order_line.filtered(lambda x: x.is_delivery)) > 0:
                record.flag_delivery = True
