# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    # -------------------------------------------------------------------------
    # EARLY PAYMENT DISCOUNT - UPDATE by MOVEO+
    # -------------------------------------------------------------------------

    def _is_eligible_for_early_payment_discount_partial(self, currency, reference_date):
        """Check if the invoice is eligible for an early payment discount on partial payments.

        Args:
            currency (recordset): The currency to check against the invoice's currency.
            reference_date (date): The reference date to compare against the discount deadline.

        Returns:
            bool: True if eligible, False otherwise.
        """
        self.ensure_one()
        try:
            # Check eligibility conditions
            has_early_discount = self.invoice_payment_term_id.early_discount
            is_within_discount_period = (
                not reference_date
                or reference_date
                <= self.invoice_payment_term_id._get_last_discount_date(
                    self.invoice_date
                )
            )
            return (
                self.currency_id == currency
                and self.move_type == "out_invoice"
                and self.payment_state == "partial"
                and has_early_discount
                and is_within_discount_period
            )
        except Exception as e:
            _logger.error(
                "Error checking eligibility for early payment discount: %s", e
            )
