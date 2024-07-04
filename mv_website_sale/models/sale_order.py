# -*- coding: utf-8 -*-
from odoo import models

QUANTITY_THRESHOLD = 4


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def check_show_warning(self):
        order_line = self.order_line.filtered(
            lambda line: line.product_id.product_tmpl_id.detailed_type == "product"
            and self.check_category_product(line.product_id.categ_id)
        )
        return (
            len(order_line) >= 1
            and sum(order_line.mapped("product_uom_qty")) < QUANTITY_THRESHOLD
        )

    def check_missing_partner_discount(self):
        order = self
        agency_discount_line = (
            order.order_line._filter_discount_agency_lines(order)
            or order.discount_agency_set
        )
        return not agency_discount_line

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

    # ==================================
    # ORM / CURD Methods
    # ==================================

    def copy(self, default=None):
        # MOVEOPLUS Override
        orders = super(SaleOrder, self).copy(default)
        orders._update_programs_and_rewards()
        orders._auto_apply_rewards()
        return orders
