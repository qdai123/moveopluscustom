from odoo import models, fields, api


class PartnerArea(models.Model):
    _name = 'mv.partner.area'
    _description = 'Cấu hình khu vực Đại lý'

    parent_id = fields.Many2one('mv.partner.area', string='Vùng (Parent)', index=True)
    name = fields.Char(string='Tên vùng', required=True)
    code_area = fields.Char(string='Mã vùng')


    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Tên vùng phải là duy nhất.')
    ]
