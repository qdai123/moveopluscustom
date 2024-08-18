# -*- coding: utf-8 -*-
from odoo.addons.mv_sale.models.sale_order import QUANTITY_THRESHOLD

from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # === MOVEOPLUS OVERRIDE === #

    def _compute_cart_info(self):
        self.so_trigger_update()
        super(SaleOrder, self)._compute_cart_info()

        for order in self:
            service_lines = order.website_order_line.filtered(
                lambda line: line.product_template_id.detailed_type == "service"
            )
            if service_lines:
                total_service_qty = sum(service_lines.mapped("product_uom_qty"))
                order.cart_quantity -= int(total_service_qty)

    # === MOVEOPLUS METHODS === #

    # /// VALIDATION

    def check_show_warning(self):
        order = self
        if not order.partner_id.is_southern_agency:
            order_line = order.order_line.filtered(
                lambda sol: sol.product_id.product_tmpl_id.detailed_type == "product"
                and order.check_category_product(sol.product_id.categ_id)
            )
            return (
                len(order_line) >= 1
                and sum(order_line.mapped("product_uom_qty")) < QUANTITY_THRESHOLD
            )

    def check_missing_partner_discount(self):
        order = self
        is_partner_agency = order.partner_agency or order.partner_id.is_agency
        agency_discount_line = (
            order.order_line._filter_discount_agency_lines(order)
            or order.discount_agency_set
        )
        return is_partner_agency and not agency_discount_line

    # /// TOOLING

    def _is_partner_agency_order(self):
        self.ensure_one()
        return (
            self.partner_id.id == request.website.user_id.sudo().partner_id.id
            and self.partner_agency
        )
