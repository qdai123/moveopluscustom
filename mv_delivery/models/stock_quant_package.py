# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import api, fields, models


class StockQuantPackage(models.Model):
    _inherit = "stock.quant.package"

    @api.depends("quant_ids", "package_type_id")
    def _compute_volume(self):
        if self.env.context.get("picking_id"):
            package_volumes = defaultdict(float)
            res_groups = self.env["stock.move.line"]._read_group(
                [
                    ("result_package_id", "in", self.ids),
                    ("product_id", "!=", False),
                    ("picking_id", "=", self.env.context["picking_id"]),
                ],
                ["result_package_id", "product_id", "product_uom_id", "quantity"],
                ["__count"],
            )
            for result_package, product, product_uom, quantity, count in res_groups:
                package_volumes[result_package.id] += (
                    count
                    * product_uom._compute_quantity(quantity, product.uom_id)
                    * product.volume
                )
        for package in self:
            volume = package.package_type_id.base_volume or 0.0
            if self.env.context.get("picking_id"):
                package.volume = volume + package_volumes[package.id]
            else:
                for quant in package.quant_ids:
                    volume += quant.quantity * quant.product_id.volume
                package.volume = volume

    def _get_default_volume_uom(self):
        return self.env[
            "product.template"
        ]._get_volume_uom_name_from_ir_config_parameter()

    def _compute_volume_uom_name(self):
        for package in self:
            package.volume_uom_name = self.env[
                "product.template"
            ]._get_volume_uom_name_from_ir_config_parameter()

    def _compute_volume_is_m_3(self):
        self.volume_is_m_3 = False
        uom_id = self.env[
            "product.template"
        ]._get_volume_uom_id_from_ir_config_parameter()
        if uom_id == self.env.ref("uom.product_uom_categ_vol"):
            self.volume_is_m_3 = True
        self.volume_uom_rounding = uom_id.rounding

    volume = fields.Float(
        compute="_compute_volume",
        digits="Volume",
        help="Total volume of all the products contained in the package.",
    )
    volume_uom_name = fields.Char(
        string="Volume unit of measure label",
        compute="_compute_volume_uom_name",
        readonly=True,
        default=_get_default_volume_uom,
    )
    volume_is_m_3 = fields.Boolean(
        "Technical field indicating whether volume uom is m³ or not (i.e. lb)",
        compute="_compute_volume_is_m_3",
    )
    volume_uom_rounding = fields.Float(
        "Technical field indicating volume's number of decimal places",
        compute="_compute_volume_is_m_3",
    )
    shipping_volume = fields.Float(
        string="Shipping Volume", help="Total volume of the package."
    )
