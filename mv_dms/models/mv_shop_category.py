# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MvShopCategory(models.Model):
    _name = "mv.shop.category"
    _description = _("Shop Category")

    name = fields.Char(
        "Name",
        index="trigram",
        required=True,
    )
    complete_name = fields.Char(
        "Complete Name",
        compute="_compute_complete_name",
        recursive=True,
        store=True,
    )
    parent_id = fields.Many2one(
        comodel_name="mv.shop.category",
        string="Parent Category",
        index=True,
        ondelete="cascade",
    )
    parent_path = fields.Char(index=True, unaccent=False)
    child_id = fields.One2many(
        "mv.shop.category",
        "parent_id",
        "Child Categories",
    )
    shop_count = fields.Integer(
        "# Shops",
        compute="_compute_shop_count",
        help="The number of shops under this category (Does not consider the children categories)",
    )
    shop_properties_definition = fields.PropertiesDefinition("Shop Properties")

    @api.depends("name", "parent_id.complete_name")
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.complete_name = "%s / %s" % (
                    category.parent_id.complete_name,
                    category.name,
                )
            else:
                category.complete_name = category.name

    def _compute_shop_count(self):
        read_group_res = self.env["mv.shop"]._read_group(
            [("mv_shop_categ_id", "child_of", self.ids)],
            ["mv_shop_categ_id"],
            ["__count"],
        )
        group_data = {categ.id: count for categ, count in read_group_res}
        for categ in self:
            shop_count = 0
            for sub_categ_id in categ.search([("id", "child_of", categ.ids)]).ids:
                shop_count += group_data.get(sub_categ_id, 0)
            categ.shop_count = shop_count

    @api.constrains("parent_id")
    def _check_category_recursion(self):
        if not self._check_recursion():
            raise ValidationError(_("You cannot create recursive categories."))

    @api.model
    def name_create(self, name):
        category = self.create({"name": name})
        return category.id, category.display_name

    @api.depends_context("hierarchical_naming")
    def _compute_display_name(self):
        if self.env.context.get("hierarchical_naming", True):
            return super()._compute_display_name()
        for record in self:
            record.display_name = record.name
