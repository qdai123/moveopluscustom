# -*- coding: utf-8 -*-
from odoo import fields, models


class CategoryJob(models.Model):
    _name = "category.job"

    code = fields.Char(string="Code", required=True)
    name = fields.Char(string="Name", required=True)
    job_ids = fields.One2many("hr.job", "category_id")
