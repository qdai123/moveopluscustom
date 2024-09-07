# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class MvProductProduct(models.Model):
    _name = "mv.product.product"
    _description = _("Product")

    partner_survey_id = fields.Many2one(
        comodel_name="mv.partner.survey",
        string="Phiếu khảo sát",
        required=True,
        index=True,
        ondelete="restrict",
    )
    partner_survey_ref = fields.Char(
        "Mã khảo sát đối tác",
        compute="_compute_partner_survey_ref",
    )
    active = fields.Boolean("Active", default=True)
    name = fields.Char(
        "Tên sản phẩm",
        compute="_compute_name",
        store=True,
        readonly=False,
        index="trigram",
    )
    product_attribute_id = fields.Many2one("mv.product.attribute", "Thuộc tính S/P")
    brand_id = fields.Many2one("mv.brand", "Thương hiệu")
    uom_id = fields.Many2one("uom.uom", "Đơn vị", related="brand_id.uom_id")
    quantity_per_month = fields.Integer("Số lượng mỗi tháng", default=0)

    _sql_constraints = [
        (
            "name_product_attribute_brand_unique",
            "UNIQUE(name, product_attribute_id, brand_id)",
            "The name of the product must be unique!",
        )
    ]

    @api.depends("product_attribute_id", "brand_id")
    def _compute_name(self):
        for product in self:
            if product.product_attribute_id and product.brand_id:
                product.name = "%s %s" % (
                    product.brand_id.name,
                    product.product_attribute_id.name,
                )

    @api.depends("partner_survey_id")
    @api.depends_context("partner_survey_ref")
    def _compute_partner_survey_ref(self):
        for product in self:
            survey_ref = self.env.context.get("partner_survey_ref")
            if survey_ref:
                product.partner_survey_ref = survey_ref
            else:
                product.partner_survey_ref = product.partner_survey_id.name
