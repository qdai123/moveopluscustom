# -*- coding: utf-8 -*-
from odoo import fields, models


class HrJob(models.Model):
    _inherit = "hr.job"

    category_id = fields.Many2one("category.job")
