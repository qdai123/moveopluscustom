# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, _, api, fields, models


class MvShop(models.Model):
    """Shop for Partner Survey"""

    _name = "mv.shop"
    _description = _("Shop")

    def _read_group_categ_id(self, categories, domain, order):
        category_ids = self.env.context.get("default_mv_brand_categ_id")
        if not category_ids and self.env.context.get("group_expand"):
            category_ids = categories._search(
                [], order=order, access_rights_uid=SUPERUSER_ID
            )
        return categories.browse(category_ids)

    partner_survey_id = fields.Many2one(
        comodel_name="mv.partner.survey",
        string="Phiếu khảo sát",
        required=True,
        index=True,
        ondelete="restrict",
    )
    name = fields.Char(string="Cửa hàng", required=True)
    street = fields.Char(string="Đường", required=True)
    country_id = fields.Many2one(
        comodel_name="res.country",
        string="Quốc gia",
        required=True,
        default=lambda self: self.env.ref("base.vn").id,
    )
    state_id = fields.Many2one(
        comodel_name="res.country.state",
        string="Thành phố",
        required=True,
        domain="[('country_id', '=', country_id)]",
    )
    district_id = fields.Many2one(
        comodel_name="res.country.district",
        string="Quận",
        required=True,
        domain="[('state_id', '=', state_id)]",
    )
    wards_id = fields.Many2one(
        comodel_name="res.country.wards",
        string="Phường",
        required=True,
        domain="[('district_id', '=', district_id)]",
    )
    address = fields.Char(string="Địa chỉ", compute="_compute_address", store=True)
    latitude = fields.Float(string="Vĩ độ", digits=(16, 5))
    longitude = fields.Float(string="Kinh độ", digits=(16, 5))
    square_meter = fields.Float(string="Diện tích (m2)", default=0)
    mv_shop_categ_id = fields.Many2one(
        "mv.shop.category",
        "Danh mục cửa hàng",
        group_expand="_read_group_categ_id",
        required=True,
    )
    color = fields.Integer("Color Index")

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name)",
            "Tên cửa hàng đã tồn tại, vui lòng chọn tên khác!",
        )
    ]

    @api.depends("street", "country_id", "state_id", "district_id", "wards_id")
    def _compute_address(self):
        for record in self:
            # Only compute address if all fields are present
            if all(
                [
                    record.street,
                    record.country_id,
                    record.state_id,
                    record.district_id,
                    record.wards_id,
                ]
            ):
                # Joining non-empty components to form the address
                record.address = ", ".join(
                    filter(
                        None,
                        [
                            record.street,
                            record.wards_id.name,
                            record.district_id.name,
                            record.state_id.name,
                            record.country_id.name,
                        ],
                    )
                )
            else:
                record.address = ""
