# -*- coding: utf-8 -*-

from odoo import models, api, fields


class BasicSalaryLine(models.Model):
    _name = 'basic.salary.line'

    salary_id = fields.Many2one("basic.salary")
    date = fields.Date(string="Date effect", required=True)
    salary = fields.Monetary(required=True, string="Value", currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related="salary_id.currency_id")
    level = fields.Integer(default=1, string="Lever", required=True)

    @api.depends('level', 'salary')
    def _compute_display_name(self):
        for record in self:
            record.display_name = "Bậc %s - lương căn bản %s %s" % (record.level, record.salary, record.currency_id.symbol)
