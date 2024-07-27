# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrContract(models.Model):
    _inherit = "hr.contract"

    salary_id = fields.Many2one("basic.salary", string="Basic salary")
    salary_line_id = fields.Many2one("basic.salary.line", string="Basic salary line")
    level = fields.Integer(string="Level")
    category_id = fields.Many2one(
        "category.job", related="job_id.category_id", store=True
    )

    @api.onchange("level", "category_id")
    def onchange_level(self):
        self.wage = 0
        self.salary_id = False
        self.salary_line_id = False
        if self.level != 0 and self.category_id:
            salary_ids = self.env["basic.salary"].search(
                [("category_id", "=", self.category_id.id)]
            )
            if len(salary_ids) < 1:
                raise ValidationError(_("Config basic salary for %s") % self.job_id)
            elif len(salary_ids) > 1:
                raise ValidationError(
                    _("More config basic salary for %s") % self.job_id
                )
            else:
                salary_id = salary_ids[0]
                line_ids = salary_id.line_ids.filtered(
                    lambda x: x.level == self.level and x.date <= fields.Date.today()
                ).sorted(lambda l: l.date)
                if len(line_ids) < 1:
                    raise ValidationError(
                        _("No found config basic salary for level %s and job %s")
                        % (self.level, self.job_id.name)
                    )
                else:
                    self.wage = line_ids[-1].salary
                    self.salary_id = line_ids[-1].salary_id.id
                    self.salary_line_id = line_ids[-1].id
