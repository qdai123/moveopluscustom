# -*- coding: utf-8 -*-

from odoo import models, api, fields, _


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    category_id = fields.Many2one("category.job", related="job_id.category_id", store=True)
    level = fields.Selection([('0', ''), ('1', 'I'), ('2', 'II'), ('3', 'III'), ('4', 'IV'), ('5', 'V'), ('6', 'VI'),
                              ('7', 'VII'), ('8', 'VIII'), ('9', 'IX')], string="Level", compute="_compute_level")

    @api.depends('contract_id')
    def _compute_level(self):
        for record in self:
            if record.contract_id:
                record.level = str(record.sudo().contract_id.level)
            else:
                record.level = '0'

class HrEmployeeBase(models.AbstractModel):
    _inherit = "hr.employee.base"

    category_id = fields.Many2one("category.job", related="job_id.category_id", store=True)
    level = fields.Selection([('0', ''), ('1', 'I'), ('2', 'II'), ('3', 'III'), ('4', 'IV'), ('5', 'V'), ('6', 'VI'),
                              ('7', 'VII'), ('8', 'VIII'), ('9', 'IX')], string="Level", compute="_compute_level")
    contract_id = fields.Many2one('hr.contract')
    @api.depends('contract_id')
    def _compute_level(self):
        for record in self:
            if record.contract_id:
                record.level = str(record.sudo().contract_id.level)
            else:
                record.level = '0'

class HrEmployeePublic(models.AbstractModel):
    _inherit = "hr.employee.public"

    category_id = fields.Char()
    level = fields.Selection([('0', ''), ('1', 'I'), ('2', 'II'), ('3', 'III'), ('4', 'IV'), ('5', 'V'), ('6', 'VI'),
                              ('7', 'VII'), ('8', 'VIII'), ('9', 'IX')], string="Level")
    contract_id = fields.Char()
