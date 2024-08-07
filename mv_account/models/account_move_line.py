# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    # -------------------------------------------------------------------------
    # REGISTER PAYMENT - WIZARD (OVERRIDE)
    # -------------------------------------------------------------------------

    def action_register_payment(self):
        """
        Register payment action for account move lines.

        This method overrides the default action to register payment, adding logic to determine
        if early payment discounts should be applied based on the invoice conditions.

        :return: dict: The action dictionary with updated context.
        """
        action = super().action_register_payment()

        invoice = self.move_id
        reference_date = fields.Date.context_today(self)

        # Simplify conditions for readability
        is_out_invoice = invoice.move_type == "out_invoice"
        is_partial_payment = invoice.payment_state == "partial"
        has_early_discount = invoice.invoice_payment_term_id.early_discount
        is_within_discount_period = (
            not reference_date
            or reference_date
            <= invoice.invoice_payment_term_id._get_last_discount_date(
                invoice.invoice_date
            )
        )

        # Combine conditions for determining if early discount applies
        apply_early_discount = (
            is_out_invoice
            and is_partial_payment
            and has_early_discount
            and is_within_discount_period
        )

        action["context"]["default_keep_apply_discount_early"] = apply_early_discount
        amount_discount_for_partial = (
            invoice.invoice_payment_term_id._get_amount_due_after_discount(
                invoice.amount_total, invoice.amount_tax
            )
            or 0.0
        )
        action["context"]["amount_discount_for_partial"] = (
            invoice.amount_total - amount_discount_for_partial
        )

        _logger.debug(f"Action context updated: {action['context']}")

        return action
