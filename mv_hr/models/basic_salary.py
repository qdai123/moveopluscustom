# -*- coding: utf-8 -*-

from odoo import models, api, fields

rule_salary = {
    'BASIC': "Lương căn bản",
    'AGC': "Phụ cấp - Ăn giữa ca",
    'XDL': "Phụ cấp - Xăng,Đi lại",
    'DT': "Phụ cấp -  Điện thoại",
    'NC': "Phụ cấp -   Nuôi con",
    'GROSS': "Tổng",
    'LTNCTT': "Lương theo ngày công tt",
    'TANGCA': "Tăng ca",
    'NANGSUAT': "Năng suất",
    'TONG': "Tổng phát sinh",
    'THUNHAPCHIUTHUE': "Thu nhập chịu thuế",
    'BHXH': "BHXH",
    'TAMUNG': "Chuyển nhượng tiền lương",
    'CONGDOAN': "Công đoàn",
    'TONGCONG': "Tổng cộng",
    'TNCTTNCN': "Thu nhập tính thuế",
    'THUETNCN': "Thuế TNCN",
    'NET': "Lương Thực Lĩnh",
}
code = [
    ('BASIC', 'BASIC'),
    ('AGC', 'AGC'),
    ('XDL', 'XDL'),
    ('DT', 'DT'),
    ('NC', 'NC'),
    ('GROSS', 'GROSS'),
    ('LTNCTT', 'LTNCTT'),
    ('TANGCA', 'TANGCA'),
    ('NANGSUAT', 'NANGSUAT'),
    ('TONG', 'TONG'),
    ('THUNHAPCHIUTHUE', 'THUNHAPCHIUTHUE'),
    ('BHXH', 'BHXH'),
    ('TAMUNG', 'TAMUNG'),
    ('CONGDOAN', 'CONGDOAN'),
    ('TONGCONG', 'TONGCONG'),
    ('TNCTTNCN', 'TNCTTNCN'),
    ('THUETNCN', 'THUETNCN'),
    ('NET', 'NET')
]


class BasicSalary(models.Model):
    _name = 'basic.salary'

    code = fields.Selection(code, string="Code", required=True)
    name = fields.Char(string="Name", required=False)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    salary = fields.Monetary(string="Salary", currency_field='currency_id')
    line_ids = fields.One2many("basic.salary.line", "salary_id")
    job_id = fields.Many2one("hr.job", string="Job position", required=False, )
    category_id = fields.Many2one("category.job", required=True)
    department_id = fields.Many2one("hr.department", related="job_id.department_id")

    @api.depends('name', 'job_id', 'code')
    def _compute_display_name(self):
        for record in self:
            if record.code not in ['', False]:
                record.name = rule_salary.get(record.code)
            if record.name not in ['', False] and record.category_id:
                record.display_name = record.name + '-' + record.category_id.name
            else:
                record.display_name = ''
