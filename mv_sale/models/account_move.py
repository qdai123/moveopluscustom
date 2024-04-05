# -*- coding: utf-8 -*-

from odoo import models, api, fields
from datetime import datetime


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        res = super(AccountMove, self).create(vals_list)
        for record in res:
            sale_id = self.env['sale.order'].search([('name', '=', record.invoice_origin)])
            if len(sale_id) > 0:
                if not sale_id.date_invoice:
                    sale_id.write({
                        'date_invoice': record.create_date,
                    })
        return res
