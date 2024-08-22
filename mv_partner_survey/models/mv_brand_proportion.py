from odoo import models, fields, api
from odoo.exceptions import ValidationError


class MVBrandProportion(models.Model):
    _name = 'mv.brand.proportion'
    _description = 'Brand Proportion'

    partner_survey_id = fields.Many2one(
        comodel_name='mv.partner.survey',
        string='Profile',
        required=True,
        index=True,
        ondelete='restrict'
    )

    brand_id = fields.Many2one(
        comodel_name='mv.brand',
        string='Hãng/Thương hiệu',
        required=True
    )

    year_participation = fields.Char(
        string='Năm tham gia',
        required=True,
        size=10
    )

    proportion = fields.Float(
        string='Tỷ trọng (%)',
        default=0
    )

    quantity_per_month = fields.Integer(
        string='Số lượng quả/tháng',
        default=0
    )

    @api.constrains('partner_survey_id', 'brand_id')
    def _check_unique_profile_brand_year(self):
        for record in self:
            domain = [
                ('partner_survey_id', '=', record.partner_survey_id.id),
                ('brand_id', '=', record.brand_id.id),
                ('id', '!=', record.id)
            ]
            existing = self.search_count(domain)
            if existing > 0:
                raise ValidationError(
                    'Không được tạo dữ liệu trùng lặp cho cùng Profile, Thương hiệu.'
                )
