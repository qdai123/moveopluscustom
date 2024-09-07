# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MvProductAttribute(models.Model):
    _name = "mv.product.attribute"
    _description = _("Product Attribute")
    _order = "sequence, name, id"

    sequence = fields.Integer("Sequence", index=True)
    name = fields.Char("Attribute", required=True)
    brand_id = fields.Many2one("mv.brand", "Brand", index=True)
    mv_product_ids = fields.Many2many(
        "mv.product.product",
        "mv_attribute_mv_product_rel",
        "mv_attribute_id",
        "mv_product_id",
        "Related Products",
        readonly=True,
    )
    number_related_mv_products = fields.Integer(
        compute="_compute_number_related_mv_products", readonly=True
    )

    _sql_constraints = [
        (
            "name_brand_unique",
            "UNIQUE(name, brand_id)",
            "Attribute names and brands must be unique!",
        )
    ]

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if args is None:
            args = []

        args += self._get_contextual_brand_filter()
        return super(MvProductAttribute, self).name_search(name, args, operator, limit)

    def _get_contextual_brand_filter(self):
        search_context = dict(self.env.context or {})
        brand_filter = []

        if search_context.get("search_default_brand_tire"):
            brand_tire = self.env.ref("mv_dms.brand_category_tire")
            brand_filter = [("brand_id.mv_brand_categ_id", "=", brand_tire.id)]
        elif search_context.get("search_default_brand_lubricant"):
            brand_lubricant = self.env.ref("mv_dms.brand_category_lubricant")
            brand_filter = [("brand_id.mv_brand_categ_id", "=", brand_lubricant.id)]
        elif search_context.get("search_default_brand_battery"):
            brand_battery = self.env.ref("mv_dms.brand_category_battery")
            brand_filter = [("brand_id.mv_brand_categ_id", "=", brand_battery.id)]

        return brand_filter

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
            "res_model": "mv.product.product",
            "view_mode": "tree,form",
            "domain": [("product_attribute_id", "=", self.id)],
        }
