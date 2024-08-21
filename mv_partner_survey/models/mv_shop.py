from odoo import models, fields, api


class MVShop(models.Model):
    _name = "mv.shop"
    _description = "Thông tin cửa hàng cho Đại lý"

    partner_survey_id = fields.Many2one(
        comodel_name="mv.partner.survey",
        string="Profile",
        required=True,
        index=True,
        ondelete="restrict",
    )
    name = fields.Char(string="Tên cửa hàng", required=True)
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
    square_meter = fields.Float(string="Diện tích (m2)", default=0)
    brand_id = fields.Many2one("mv.brand", string="Hãng/Thương hiệu", required=True)

    _sql_constraints = [
        (
            "unique_shop",
            "unique(address, brand_id)",
            "Mỗi một Shop là duy nhất theo địa chỉ và thương hiệu!",
        )
    ]

    @api.depends("street", "country_id", "state_id", "district_id", "wards_id")
    def _compute_address(self):
        for record in self:
            if all(
                [
                    record.street,
                    record.country_id,
                    record.state_id,
                    record.district_id,
                    record.wards_id,
                ]
            ):
                address_components = [
                    record.street,
                    record.wards_id.name,
                    record.district_id.name,
                    record.state_id.name,
                    record.country_id.name,
                ]
                record.address = ", ".join(address_components)
            else:
                record.address = ""
