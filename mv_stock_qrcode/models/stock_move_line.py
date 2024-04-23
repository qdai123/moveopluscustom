# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    qr_code_prefix = fields.Char(
        string="QR-Code Prefix",
        help="Combine Week Number with Product Barcode",
        readonly=True,
    )
    qr_code_suffix = fields.Char(
        string="QR-Code Suffix",
        help="Fix the number at the last of QR-Code, Size default = 5 (E.g: 00001)",
        readonly=True,
    )

    # INHERIT Fields:
    inventory_period_name = fields.Char(
        related="inventory_period_id.week_number_str",
        store=True,
        help="Make this field can call by `search_read()`",
    )

    def _get_fields_stock_barcode(self):
        fields = super(StockMoveLine, self)._get_fields_stock_barcode()
        fields += ["qr_code_prefix", "qr_code_suffix"]
        return fields
