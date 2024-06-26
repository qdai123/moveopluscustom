# -*- coding: utf-8 -*-
import logging

from odoo import models, _

from odoo.addons.biz_zalo_common.models.common import convert_valid_phone_number

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def action_send_message_zns(self):
        self.ensure_one()

        picking = self
        order = picking.sale_id
        if not order:
            _logger.error("No associated sale order found for the stock picking.")
            return

        view_id = self.env.ref("biz_zalo_zns.view_zns_send_message_wizard_form")
        if not view_id:
            _logger.error(
                "View 'biz_zalo_zns.view_zns_send_message_wizard_form' not found."
            )
            return

        phone_number = order.partner_id.phone if order.partner_id else None
        valid_phone_number = (
            convert_valid_phone_number(phone_number) if phone_number else False
        )

        return {
            "name": _("Send Message ZNS"),
            "type": "ir.actions.act_window",
            "res_model": "zns.send.message.wizard",
            "view_id": view_id.id,
            "views": [(view_id.id, "form")],
            "context": {
                "default_use_type": self._name,
                "default_picking_id": picking.id,
                "default_order_id": order.id,
                "default_phone": valid_phone_number,
            },
            "target": "new",
        }
