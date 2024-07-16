# -*- coding: utf-8 -*-
import logging

from odoo.addons.biz_zalo_common.models.common import convert_valid_phone_number

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = "stock.picking"

    # === PARTNER FIELDS ===#
    short_name = fields.Char(related="partner_id.short_name", store=True)
    partner_delivery_address = fields.Char(
        "Partner Delivery Address", compute="_compute_partner_address", store=True
    )
    partner_delivery_address_advanced = fields.Char(
        "Partner Delivery Address (Advanced)",
        compute="_compute_partner_address",
        store=True,
    )

    # === SALE ORDER FIELDS ===#
    order_display_name = fields.Char(related="sale_id.name", store=True)
    order_date_confirmed = fields.Date(
        "Order Date Confirmed", compute="_compute_order_date_confirmed", store=True
    )

    @api.depends("partner_id")
    def _compute_partner_address(self):
        for picking in self:
            partner = picking.partner_id
            address_components = [partner.street]
            # Filter out any False or None values before joining
            partner_address = ", ".join(filter(None, address_components))

            address_advanced_components = [
                partner.wards_id.name,
                partner.district_id.name,
                partner.state_id.name,
            ]
            # Filter out any False or None values before joining
            partner_address_advanced = ", ".join(
                filter(None, address_advanced_components)
            )

            picking.partner_delivery_address = partner_address
            picking.partner_delivery_address_advanced = partner_address_advanced

    @api.depends("sale_id", "sale_id.date_order")
    def _compute_order_date_confirmed(self):
        for picking in self:
            picking.order_date_confirmed = (
                picking.sale_id.date_order.date() if picking.sale_id else None
            )

    # /// ACTIONS ///

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

        # ZNS Template:
        zns_template = self.env["zns.template"].search(
            [
                ("active", "=", True),
                ("sample_data", "!=", False),
                ("use_type", "=", picking._name),
            ],
            limit=1,
        )

        return {
            "name": _("Send Message ZNS"),
            "type": "ir.actions.act_window",
            "res_model": "zns.send.message.wizard",
            "view_id": view_id.id,
            "views": [(view_id.id, "form")],
            "context": {
                "default_phone": valid_phone_number,
                "default_template_id": zns_template.id if zns_template else False,
                "default_use_type": picking._name,
                "default_tracking_id": picking.id,
                "default_picking_id": picking.id,
                "default_order_id": order.id,
            },
            "target": "new",
        }
