# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_open_delivery_wizard(self):
        action = super(SaleOrder, self).action_open_delivery_wizard()
        action["context"]["default_total_volume"] = self._get_estimated_volume()
        return action

    shipping_volume = fields.Float(
        "Shipping Volume",
        compute="_compute_shipping_volume",
        store=True,
        readonly=False,
    )

    @api.depends("order_line.product_uom_qty", "order_line.product_uom")
    def _compute_shipping_volume(self):
        for order in self:
            order.shipping_weight = order._get_estimated_volume()

    def _get_estimated_volume(self):
        self.ensure_one()
        if self.delivery_set:
            return self.shipping_volume
        volume = 0.0
        for order_line in self.order_line.filtered(
            lambda l: l.product_id.type in ["product", "consu"]
            and not l.is_delivery
            and not l.display_type
            and l.product_uom_qty > 0
        ):
            volume += order_line.product_qty * order_line.product_id.volume
        return volume
