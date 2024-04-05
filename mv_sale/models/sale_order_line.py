# -*- coding: utf-8 -*-

from odoo import models, api, fields
from odoo import http


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    hidden_show_qty = fields.Boolean(help="Do not show change qty in website", default=False, copy=False)
    discount_line_id = fields.Many2one("mv.compute.discount.line")
    code_product = fields.Char(help="Do not recompute discount")

    # SUPPORT Fields:
    is_sales_manager = fields.Boolean(compute='_compute_is_sales_manager', default=False)

    def _compute_is_sales_manager(self):
        for user in self:
            if self.env.user.has_group("sales_team.group_sale_manager"):
                user.is_sales_manager = True
            else:
                user.is_sales_manager = False

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        fields = super(SaleOrderLine, self).fields_get(allfields, attributes)
        return fields

    def _is_not_sellable_line(self):
        return self.hidden_show_qty or super()._is_not_sellable_line()

    @api.depends('state')
    def _compute_product_uom_readonly(self):
        # OVERRIDE to set access groups of Sales
        for line in self:
            # line.ids checks whether it's a new record not yet saved
            line.product_uom_readonly = line.ids and line.state in ['sale', 'cancel'] or (
                    not line.is_sales_manager and line.product_template_id.detailed_type == 'service')

    @api.depends('product_id', 'state', 'qty_invoiced', 'qty_delivered')
    def _compute_product_updatable(self):
        # OVERRIDE to set access groups of Sales
        for line in self:
            if line.state == 'cancel':
                line.product_updatable = False
            elif line.state == 'sale' and (
                    line.order_id.locked
                    or line.qty_invoiced > 0
                    or line.qty_delivered > 0
            ):
                line.product_updatable = False
            elif line.state not in ["cancel", "sale"] and not line.is_sales_manager and line.product_type == 'service':
                line.product_updatable = True
            else:
                line.product_updatable = True

    def unlink(self):
        for record in self:
            if record.product_id and record.product_id.default_code and record.product_id.default_code.find(
                    'Delivery_') > -1:
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
