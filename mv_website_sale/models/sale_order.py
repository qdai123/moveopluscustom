# -*- coding: utf-8 -*-
from odoo.addons.mv_sale.models.sale_order import QUANTITY_THRESHOLD

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # === MOVEOPLUS OVERRIDE === #

    def _compute_cart_info(self):
        # Call the parent class's _compute_cart_info method
        super(SaleOrder, self)._compute_cart_info()

        # Iterate over each order in the recordset
        for order in self:
            # Calculate the total quantity of all service lines that are not reward lines
            # This is done by summing the "product_uom_qty" field of each line in the order's "website_order_line" field
            # that has a product with a "detailed_type" not equal to "product" and is not a reward line
            service_lines_qty = sum(
                line.product_uom_qty
                for line in order.website_order_line
                if line.product_id.product_tmpl_id.detailed_type != "product"
                and not line.is_reward_line
            )

            # Subtract the total quantity of service lines from the order's "cart_quantity"
            # The int() function is used to ensure that the result is an integer
            order.cart_quantity -= int(service_lines_qty)
            order._compute_partner_bonus()
            order._compute_bonus_order_line()

    # /// ORM/CRUD

    def copy(self, default=None):
        orders = super(SaleOrder, self).copy(default)

        orders._update_programs_and_rewards()
        orders._auto_apply_rewards()

        return orders

    # === MOVEOPLUS METHODS === #

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
