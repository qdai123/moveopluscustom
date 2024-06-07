# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class MvWhitePlaceDiscountLine(models.Model):
    _name = "mv.white.place.discount.line"
    _description = _("MOVE PLUS White Places Discount Line (%)")
    _order = "discount"
    _rec_name = "discount"
    _rec_names_search = ["discount"]

    parent_id = fields.Many2one("mv.discount", readonly=True)
    pricelist_id = fields.Many2one("product.pricelist", "Chính sách giá")
    quantity = fields.Integer("Số lượng")
    discount = fields.Float("Chiết khấu (%)", digits=(16, 2))

    @api.onchange("pricelist_id")
    def _onchange_pricelist(self):
        self.discount = 0
        if self.pricelist_id and len(self.pricelist_id.item_ids) > 0:
            item_id = self.pricelist_id.item_ids[0]
            if item_id.compute_price == "percentage":
                self.discount = item_id.percent_price
