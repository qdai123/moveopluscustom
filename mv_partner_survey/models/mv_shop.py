from odoo import models, fields, api


class MVShop(models.Model):
    _name = 'mv.shop'
    _description = 'Thông tin cửa hàng cho Đại lý'

    _sql_constraints = [
        ('unique_shop', 'unique(address, brand_id)', 'Mỗi một Shop là duy nhất theo địa chỉ và thương hiệu!')
    ]

    partner_survey_id = fields.Many2one(
        'mv.partner.survey',
        string='Profile',
        required=True,
        index=True,
        # ondelete="set null"
    )
    name = fields.Char(string='Tên cửa hàng', required=True)
    street = fields.Char(string='Đường', required=True)
    country_id = fields.Many2one(
        'res.country',
        string='Quốc gia',
        required=True
    )
    state_id = fields.Many2one(
        'res.country.state',
        string='Thành phố',
        required=True,
        # domain=[('country_id', '=', country_id)]
    )
    district_id = fields.Many2one(
        'res.country.district',
        string='Quận',
        required=True,
        # domain=[('state_id', '=', state_id)]
    )
    wards_id = fields.Many2one(
        'res.country.wards',
        string='Phường',
        required=True,
        # domain=[('district_id', '=', district_id)]
    )
    address = fields.Char(string='Địa chỉ')
    square_meter = fields.Float(string='Diện tích (m2)', default=0)
    brand_id = fields.Many2one(
        'mv.brand',
        string='Hãng/Thương hiệu',
        required=True
    )

    @api.depends('street', 'country_id', 'state_id', 'district_id', 'wards_id')
    def _compute_address(self):
        for record in self:
            if record.street and record.country_id and record.state_id and record.district_id and record.wards_id:
                record.address = f"{record.street}, {record.wards_id.name}, {record.district_id.name}, {record.state_id.name}, {record.country_id.name}"
            else:
                record.address = ''
