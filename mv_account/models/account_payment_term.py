# -*- coding: utf-8 -*-
from odoo import models


class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"

    # /// ORM Methods ///

    def _get_amount_due_after_discount(self, total_amount, untaxed_amount):
        return super()._get_amount_due_after_discount(total_amount, untaxed_amount)
