# -*- coding:utf-8 -*-
from odoo import models


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def compute_sheet(self):
        try:
            self.contract_id.onchange_level()
        except:
            pass
        return super(HrPayslip, self).compute_sheet()
