# -*- coding: utf-8 -*-
from odoo import models


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
        for order in self:
            # If the partner has a quantity threshold value set
            if order.partner_id.quantity_threshold_value > 0:
                if not order.partner_id.is_southern_agency:
                    order_line = order.order_line.filtered(
                        lambda sol: sol.product_id.product_tmpl_id.detailed_type
                        == "product"
                        and order.check_category_product(sol.product_id.categ_id)
                    )
                    total_qty = sum(order_line.mapped("product_uom_qty"))

                    # Check if total quantity is less than the partner's threshold value
                    if (
                        len(order_line) >= 1
                        and total_qty < order.partner_id.quantity_threshold_value
                    ):
                        return True
            else:
                if not order.partner_id.is_southern_agency:
                    order_line = order.order_line.filtered(
                        lambda sol: sol.product_id.product_tmpl_id.detailed_type
                        == "product"
                        and order.check_category_product(sol.product_id.categ_id)
                    )
                    total_qty = sum(order_line.mapped("product_uom_qty"))

        return False

    def check_missing_partner_discount(self):
        order = self
        is_partner_agency = order.partner_agency or order.partner_id.is_agency
        agency_discount_line = (
            order.order_line._filter_agency_lines(order) or order.discount_agency_set
        )
        return is_partner_agency and not agency_discount_line

    # /// TOOLING

    def _is_partner_agency_order(self):
        self.ensure_one()
        return (
            self.partner_id.id == request.website.user_id.sudo().partner_id.id
            and self.partner_agency
        )
