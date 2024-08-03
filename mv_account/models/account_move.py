# -*- coding: utf-8 -*-
import logging

from odoo import models

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    def _compute_payments_widget_reconciled_info(self):
        """
        Compute the payments widget reconciled information.

        This method updates the payments widget with early payment discount information
        if the invoice is eligible for such discounts.

        :return: None
        """
        _logger.debug("Starting '_compute_payments_widget_reconciled_info'.")

        super()._compute_payments_widget_reconciled_info()
        for move in self:
            if (
                move.invoice_payments_widget
                and move.state == "posted"
                and move.is_invoice(include_receipts=True)
            ):
                early_discount = move.invoice_payment_term_id.early_discount
                early_discount_percentage = (
                    move.invoice_payment_term_id.discount_percentage
                )
                early_discount_date = (
                    move.invoice_payment_term_id._get_last_discount_date(
                        move.invoice_date
                    )
                )
                if (
                    early_discount
                    and not move.invoice_date
                    or early_discount_date
                    and move.invoice_date <= early_discount_date
                ):
                    amount_early_discount = (
                        move.amount_total
                        - move.invoice_payment_term_id._get_amount_due_after_discount(
                            move.amount_total, move.amount_tax
                        )
                    )
                    move.invoice_payments_widget["content"][0].update(
                        {
                            "is_early_discount": True,
                            "early_discount": f"{early_discount_percentage} %",
                            "amount_early_discount": amount_early_discount or 0.0,
                        }
                    )

            _logger.debug("Completed '_compute_payments_widget_reconciled_info'.")

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
