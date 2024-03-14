# -*- coding: utf-8 -*-

from odoo import models, api, fields
from datetime import datetime


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_post(self):
        if self.invoice_origin not in ('', False):
            sale_id = self.env['sale.order'].search([('name', '=', self.invoice_origin)])
            if len(sale_id) > 0:
                sale_id.write({
                    'date_invoice': datetime.now()
                })
        return super().action_post()
