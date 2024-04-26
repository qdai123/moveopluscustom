# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models, _


class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.depends(
        "move_line_ids",
        "move_line_ids.result_package_id",
        "move_line_ids.product_uom_id",
        "move_line_ids.quantity",
    )
    def _compute_bulk_volume(self):
        picking_volume = defaultdict(float)
        res_groups = self.env["stock.move.line"]._read_group(
            [
                ("picking_id", "in", self.ids),
                ("product_id", "!=", False),
                ("result_package_id", "=", False),
            ],
            ["picking_id", "product_id", "product_uom_id", "quantity"],
            ["__count"],
        )
        for picking, product, product_uom, quantity, count in res_groups:
            picking_volume[picking.id] += (
                count
                * product_uom._compute_quantity(quantity, product.uom_id)
                * product.volume
            )
        for picking in self:
            picking.volume_bulk = picking_volume[picking.id]

    @api.depends(
        "move_line_ids.result_package_id",
        "move_line_ids.result_package_id.shipping_volume",
        "volume_bulk",
    )
    def _compute_shipping_volume(self):
        for picking in self:
            # if shipping volume is not assigned => default to calculated product volume
            picking.shipping_volume = picking.volume_bulk + sum(
                [pack.shipping_volume or pack.volume for pack in picking.package_ids]
            )

    def _get_default_volume_uom(self):
        return self.env[
            "product.template"
        ]._get_volume_uom_name_from_ir_config_parameter()

    def _compute_volume_uom_name(self):
        for package in self:
            package.volume_uom_name = self.env[
                "product.template"
            ]._get_volume_uom_name_from_ir_config_parameter()

    volume_uom_name = fields.Char(
        string="Volume unit of measure label",
        compute="_compute_volume_uom_name",
        readonly=True,
        default=_get_default_volume_uom,
    )
    shipping_volume = fields.Float(
        "Volume for Shipping",
        compute="_compute_shipping_volume",
        help="Total volume of packages and products not in a package. "
        "Packages with no shipping volume specified will default to their products' total volume. "
        "This is the volume used to compute the cost of the shipping.",
    )
    volume_bulk = fields.Float(
        "Bulk Volume",
        compute="_compute_bulk_volume",
        help="Total volume of products which are not in a package.",
    )
