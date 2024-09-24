# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class MvPromoteDiscountLine(models.Model):
    _name = "mv.promote.discount.line"
    _description = _("MOVEO PLUS Promote Discount Line (%)")
    _order = "promote_discount"
    _rec_names_search = ["name", "promote_discount"]

    @api.model
    def name_get(self):
        res = []
        for record in self:
            if self._context.get("wizard_promote_discount_search", False):
                name_fmt = "{} % ({} - {})".format(
                    record.promote_discount,
                    record.quantity_minimum,
                    record.quantity_maximum,
                )
                res.append((record.id, name_fmt))
        return res

    name = fields.Char(compute="_compute_name", store=True)
    parent_id = fields.Many2one("mv.discount", readonly=True)
    pricelist_id = fields.Many2one("product.pricelist", "Chính sách giá")
    quantity_minimum = fields.Integer("Số lượng Min")
    quantity_maximum = fields.Integer("Số lượng Max")
    promote_discount = fields.Float("Chiết khấu khuyến khích (%)", digits=(16, 2))

    @api.depends("promote_discount", "quantity_minimum", "quantity_maximum")
    def _compute_name(self):
        for record in self:
            if (
                record.promote_discount
                and record.quantity_minimum
                and record.quantity_maximum
            ):
                record.name = "{} % ({} - {})".format(
                    record.promote_discount,
                    record.quantity_minimum,
                    record.quantity_maximum,
                )

    @api.onchange("pricelist_id")
    def _onchange_pricelist(self):
        self.promote_discount = 0
        if self.pricelist_id and len(self.pricelist_id.item_ids) > 0:
            item_id = self.pricelist_id.item_ids[0]
            if item_id.compute_price == "percentage":
                self.promote_discount = item_id.percent_price
