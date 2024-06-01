# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        for record in self:
            if record.invoice_origin not in ("", False):
                sale_id = self.env["sale.order"].search(
                    [("name", "=", record.invoice_origin)]
                )
                if len(sale_id) > 0:
                    if not sale_id.date_invoice:
                        sale_id.write({"date_invoice": datetime.now()})
        return super().action_post()
