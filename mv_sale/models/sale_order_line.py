# -*- coding: utf-8 -*-

from odoo import models, api, fields


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    hidden_show_qty = fields.Boolean(help="Do not show change qty in website", default=False, copy=False)
    discount_line_id = fields.Many2one("mv.compute.discount.line")

    def _is_not_sellable_line(self):
        return self.hidden_show_qty or super()._is_not_sellable_line()

    def unlink(self):
        order_id = self.order_id
        res = super().unlink()
        order_line = order_id.order_line.filtered(lambda x: x.hidden_show_qty)
        if len(order_line) > 0:
            order_id.partner_id.write({
                'amount': order_id.partner_id.amount + order_id.bonus_order
            })
            order_id.write({
                'bonus_order': 0
            })
            order_line.unlink()
        return res

    def write(self, vals):
        res = super().write(vals)
        return res
        

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        order_id = res[0].order_id
        order_line = order_id.order_line.filtered(lambda x: x.hidden_show_qty)
        if len(order_line) > 0 and order_line[0].id not in res.ids:
            order_line.unlink()
        return res
