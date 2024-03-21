# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class SaleAdvancePaymentInv(models.TransientModel):
    _inherit = 'sale.advance.payment.inv'

    # def create_invoices(self):
    #     line_ids = self.sale_order_ids.order_line.filtered(lambda x: x.product_id.detailed_type == 'product')
    #     for line_id in line_ids:
    #         line_id.write({
    #             'qty_invoiced': line_id.product_uom_qty
    #         })
    #     return super().create_invoices()
