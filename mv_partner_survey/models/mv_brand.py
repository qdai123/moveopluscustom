from odoo import models, fields, api, _


class MvBrand(models.Model):
    _name = 'mv.brand'
    _description = 'Cấu hình hãng lốp/ Thương hiệu'

    name = fields.Char(string='Tên hãng', required=True)
    type = fields.Selection([
        ('size_lop', 'Size Lốp'),
        ('lubricant', 'Dầu nhớt')
    ], string='Loại', required=True, default='size_lop')

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Mỗi một Hãng lốp/Thương hiệu phải là DUY NHẤT!')
    ]
