# -*- coding: utf-8 -*-

from odoo import models, api, fields
from odoo import http


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    hidden_show_qty = fields.Boolean(help="Do not show change qty in website", default=False, copy=False)
    discount_line_id = fields.Many2one("mv.compute.discount.line")
    code_product = fields.Char(help="Do not recompute discount")

    def _is_not_sellable_line(self):
        return self.hidden_show_qty or super()._is_not_sellable_line()

    def unlink(self):
        for record in self:
            if record.product_id and record.product_id.default_code and record.product_id.default_code.find('Delivery_') > -1:
                pass
            else:
                order_id = record.order_id
                order_id.partner_id.write({
                    'amount': order_id.partner_id.amount + order_id.bonus_order
                })
                order_id.write({
                    'bonus_order': 0
                })
        return super().unlink()

    def write(self, vals):
        res = super().write(vals)
        for record in self:
            if record.hidden_show_qty or record.reward_id:
                return res
            else:
                order_id = record.order_id
                order_line = order_id.order_line.filtered(lambda x: x.product_id.default_code == 'CKT')
                if vals.get('product_uom_qty', False) and len(order_line) > 0:
                    order_line.unlink()
                return res
