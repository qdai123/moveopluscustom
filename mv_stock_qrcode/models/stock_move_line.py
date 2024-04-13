# -*- coding: utf-8 -*-
from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    number_call = fields.Integer(
        default=0,
        string="Number Call",
        help="Help to find the max of number for Lot/Serial Number",
    )

    def _get_fields_stock_barcode(self):
        fields = super(StockMoveLine, self)._get_fields_stock_barcode()
        fields += ["number_call"]
        return fields
