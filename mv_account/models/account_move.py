# -*- coding: utf-8 -*-
from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # EARLY PAYMENT DISCOUNT (OVERRIDE)
    # -------------------------------------------------------------------------

    def _is_eligible_for_early_payment_discount_partial(self, currency, reference_date):
        self.ensure_one()
        return (
            self.currency_id == currency
            and self.move_type
            in ("out_invoice", "out_receipt", "in_invoice", "in_receipt")
            and self.invoice_payment_term_id.early_discount
            and (
                not reference_date
                or reference_date
                <= self.invoice_payment_term_id._get_last_discount_date(
                    self.invoice_date
                )
            )
            and self.payment_state == "partial"
        )
