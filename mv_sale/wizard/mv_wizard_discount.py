# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MvWizardDiscount(models.TransientModel):
    _name = 'mv.wizard.discount'
    _description = 'Thêm chiết khấu tháng'

    amount = fields.Float(string="Số tiền sẽ chiết khấu", digits='Product Price')
    sale_id = fields.Many2one("sale.order")
    partner_id = fields.Many2one("res.partner")
    amount_partner = fields.Integer(related="partner_id.amount", string="Số tiền chiết khấu hiện có", digits='Product Price')
    bonus_max = fields.Float(string="Số tiền có thể chiết khấu tối đa", related="sale_id.bonus_max", digits='Product Price')
    bonus_order = fields.Float(related="sale_id.bonus_order", string="Số tiền đã chiết khấu", digits='Product Price')

    def button_confirm(self):
        self.sudo().sale_id.compute_discount_for_partner(self.amount)
