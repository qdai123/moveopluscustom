# -*- coding:utf-8 -*-

from odoo import api, Command, fields, models, _


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def compute_sheet(self):
        try:
            self.contract_id.onchange_level()
        except:
            pass
        return super(HrPayslip, self).compute_sheet()
