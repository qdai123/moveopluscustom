# -*- coding: utf-8 -*-
from odoo import models


class DeliveryCarrier(models.Model):
    _inherit = "delivery.carrier"

    def _get_price_available(self, order):
        self.ensure_one()
        self_sudo = self.sudo()
        order = order.sudo()
        weight = volume = quantity = 0
        total_delivery = 0.0

        # Filter out cancelled and non-product lines
        valid_lines = order.order_line.filtered(
            lambda rec_line: rec_line.state != "cancel"
            and rec_line.product_id
            and not rec_line.is_delivery
            and rec_line.product_id.type != "service"
        )

        for line in valid_lines:
            if line.is_delivery:
                total_delivery += line.price_total

            qty = line.product_uom._compute_quantity(
                line.product_uom_qty, line.product_id.uom_id
            )
            weight += (line.product_id.weight or 0.0) * qty
            volume += (line.product_id.volume or 0.0) * qty
            quantity += qty

        total = (order.total_price_after_discount or 0.0) - total_delivery
        total = self_sudo._compute_currency(order, total, "pricelist_to_company")

        # weight is either,
        # 1- weight chosen by user in choose.delivery.carrier wizard passed by context
        # 2- saved weight to use on sale order
        # 3- total order line weight as fallback
        weight = (
            self_sudo.env.context.get("order_weight") or order.shipping_weight or weight
        )

        return self_sudo._get_price_from_picking(total, weight, volume, quantity)
