# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MvSProductAttribute(models.Model):
    _name = "mv.product.attribute"
    _description = _("Product Attribute")

    sequence = fields.Integer("Sequence", index=True)
    name = fields.Char("Attribute", required=True)
    mv_product_ids = fields.Many2many("mv.product.product", string="Related Products")
    number_related_mv_products = fields.Integer(
        compute="_compute_number_related_mv_products"
    )

    @api.depends("mv_product_ids")
    def _compute_number_related_mv_products(self):
        for mvpa in self:
            mvpa.number_related_mv_products = len(mvpa.mv_product_ids)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_used_on_mv_product(self):
        for mvpa in self:
            if mvpa.number_related_mv_products:
                raise UserError(
                    _(
                        "You cannot delete the attribute %(attribute)s because it is used on the"
                        " following products:\n%(products)s",
                        attribute=mvpa.display_name,
                        products=", ".join(mvpa.mv_product_ids.mapped("display_name")),
                    )
                )

    def action_open_related_mv_products(self):
        return {
            "type": "ir.actions.act_window",
            "name": _("Related Products"),
            "res_model": "product.product",
            "view_mode": "tree,form",
            "domain": [("mv_product_attribute_id", "=", self.id)],
        }
