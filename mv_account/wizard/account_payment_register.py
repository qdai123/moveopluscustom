# -*- coding: utf-8 -*-
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    # === FIELDS ===
    keep_apply_discount_early = fields.Boolean(default=False, readonly=True)
    amount_discount_for_partial = fields.Monetary(
        compute="_compute_amount_discount_for_partial",
        currency_field="currency_id",
        store=True,
    )

    @api.onchange("payment_date")
    def _onchange_payment_date(self):
        """
        Handle changes to the payment date.

        This method checks if the payment date is within the valid range and updates the amount
        and payment difference accordingly.

        :return: dict: A warning message if the payment date is invalid, otherwise None.
        """
        if self.payment_date:

            batch_result = self._get_batches()[0]
            moves = batch_result["lines"].mapped("move_id")
            for move in moves:
                is_eligible_for_early_payment_discount = (
                    move._is_eligible_for_early_payment_discount(
                        move.currency_id, self.payment_date
                    )
                    or move._is_eligible_for_early_payment_discount_partial(
                        move.currency_id, self.payment_date
                    )
                )
                self.keep_apply_discount_early = is_eligible_for_early_payment_discount

            if self.keep_apply_discount_early:
                self._compute_amount_discount_for_partial()
                self._compute_amount()

    def _get_total_amount_using_same_currency(
        self, batch_result, early_payment_discount=True
    ):
        """
        Compute the total amount using the same currency for the given batch result.

        This method calculates the total amount for the batch result, considering early payment discounts
        if applicable.

        :param batch_result: The batch result containing the lines to process.
        :param early_payment_discount: Boolean indicating whether to consider early payment discounts.
        :return: Tuple containing the absolute total amount and the mode.
        """
        _logger.debug("Starting '_get_total_amount_using_same_currency' computation.")

        self.ensure_one()
        amount = 0.0
        mode = False
        moves = batch_result["lines"].mapped("move_id")

        try:
            for move in moves:
                is_eligible_for_early_payment_discount = (
                    move._is_eligible_for_early_payment_discount(
                        move.currency_id, self.payment_date
                    )
                )
                if early_payment_discount and (
                    is_eligible_for_early_payment_discount
                    or self.keep_apply_discount_early
                ):
                    amount += (
                        move.invoice_payment_term_id._get_amount_due_after_discount(
                            move.amount_total, move.amount_tax
                        )
                    )
                    mode = "early_payment"
                else:
                    for aml in batch_result["lines"].filtered(
                        lambda l: l.move_id.id == move.id
                    ):
                        amount += aml.amount_residual_currency
                _logger.debug(f"Move {move.id}: amount = {amount}, mode = {mode}")

            return abs(amount), mode

        except Exception as e:
            _logger.error(f"Error in '_get_total_amount_using_same_currency': {e}")
            return 0, mode

    @api.depends("keep_apply_discount_early")
    @api.depends_context("amount_discount_for_partial")
    def _compute_amount_discount_for_partial(self):
        """
        Compute the amount discount for partial payments.

        This method calculates the amount discount for partial payments based on the context,
        whether the wizard can be edited, and if early payment discounts are applied.

        :return: None
        """
        for wizard in self:
            amount_discount_by_context = self.env.context.get(
                "amount_discount_for_partial"
            )
            if (
                wizard.can_edit_wizard
                and wizard.keep_apply_discount_early
                and amount_discount_by_context
            ):
                wizard.amount_discount_for_partial = amount_discount_by_context
            else:
                wizard.amount_discount_for_partial = 0.0

    @api.depends(
        "can_edit_wizard",
        "keep_apply_discount_early",
        "source_amount",
        "source_amount_currency",
        "source_currency_id",
        "company_id",
        "currency_id",
        "payment_date",
    )
    def _compute_amount(self):
        """
        Compute the amount for the payment wizard.

        This method calculates the amount based on whether the wizard can be edited,
        if early payment discounts are applied, and other relevant fields.

        :return: None
        """
        for wizard in self:

            batch_result = self._get_batches()[0]
            moves = batch_result["lines"].mapped("move_id")
            for move in moves:
                is_eligible_for_early_payment_discount = (
                    move._is_eligible_for_early_payment_discount(
                        move.currency_id, wizard.payment_date
                    )
                    or move._is_eligible_for_early_payment_discount_partial(
                        move.currency_id, wizard.payment_date
                    )
                )
                wizard.keep_apply_discount_early = (
                    is_eligible_for_early_payment_discount
                )

            if (
                not wizard.journal_id
                or not wizard.currency_id
                or not wizard.payment_date
            ):
                wizard.amount = wizard.amount
            elif (
                not wizard.keep_apply_discount_early
                and wizard.source_currency_id
                and wizard.can_edit_wizard
            ):
                batch_result = wizard._get_batches()[0]
                wizard.amount = (
                    wizard._get_total_amount_in_wizard_currency_to_full_reconcile(
                        batch_result
                    )[0]
                )
            elif (
                wizard.keep_apply_discount_early
                and wizard.source_currency_id
                and wizard.can_edit_wizard
            ):
                batch_result = wizard._get_batches()[0]
                total_amount_residual_in_wizard_currency = (
                    wizard._get_total_amount_in_wizard_currency_to_full_reconcile(
                        batch_result, early_payment_discount=False
                    )[0]
                )
                wizard.amount = (
                    total_amount_residual_in_wizard_currency
                    - wizard.amount_discount_for_partial
                )
            else:
                wizard.amount = None

    @api.depends(
        "can_edit_wizard",
        "amount",
        "keep_apply_discount_early",
        "amount_discount_for_partial",
    )
    def _compute_payment_difference(self):
        for wizard in self:
            if (
                not wizard.keep_apply_discount_early
                and wizard.can_edit_wizard
                and wizard.payment_date
            ):
                batch_result = wizard._get_batches()[0]
                total_amount_residual_in_wizard_currency = (
                    wizard._get_total_amount_in_wizard_currency_to_full_reconcile(
                        batch_result, early_payment_discount=False
                    )[0]
                )
                wizard.payment_difference = (
                    total_amount_residual_in_wizard_currency - wizard.amount
                )
            elif (
                wizard.keep_apply_discount_early
                and wizard.can_edit_wizard
                and wizard.payment_date
            ):
                wizard.payment_difference = wizard.amount_discount_for_partial
            else:
                wizard.payment_difference = 0.0

    # -------------------------------------------------------------------------
    # BUSINESS METHODS (OVERRIDE)
    # -------------------------------------------------------------------------

    def _create_payment_vals_from_wizard(self, batch_result):
        keep_open_for_early_payment_discount = self.keep_apply_discount_early

        payment_vals = {
            "date": self.payment_date,
            "amount": self.amount,
            "payment_type": self.payment_type,
            "partner_type": self.partner_type,
            "ref": self.communication,
            "journal_id": self.journal_id.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "partner_id": self.partner_id.id,
            "partner_bank_id": self.partner_bank_id.id,
            "payment_method_line_id": self.payment_method_line_id.id,
            "destination_account_id": self.line_ids[0].account_id.id,
            "write_off_line_vals": [],
        }

        if self.payment_difference_handling == "reconcile":
            if self.early_payment_discount_mode:
                epd_aml_values_list = []
                for aml in batch_result["lines"]:
                    if (
                        aml.move_id._is_eligible_for_early_payment_discount(
                            self.currency_id, self.payment_date
                        )
                        or keep_open_for_early_payment_discount
                    ):
                        epd_aml_values_list.append(
                            {
                                "aml": aml,
                                "amount_currency": -aml.amount_residual_currency,
                                "balance": aml.currency_id._convert(
                                    -aml.amount_residual_currency,
                                    aml.company_currency_id,
                                    date=self.payment_date,
                                ),
                            }
                        )

                open_amount_currency = self.payment_difference * (
                    -1 if self.payment_type == "outbound" else 1
                )
                open_balance = self.currency_id._convert(
                    open_amount_currency,
                    self.company_id.currency_id,
                    self.company_id,
                    self.payment_date,
                )
                early_payment_values = self.env[
                    "account.move"
                ]._get_invoice_counterpart_amls_for_early_payment_discount(
                    epd_aml_values_list, open_balance
                )
                for aml_values_list in early_payment_values.values():
                    payment_vals["write_off_line_vals"] += aml_values_list

            elif not self.currency_id.is_zero(self.payment_difference):
                if self.payment_type == "inbound":
                    # Receive money.
                    write_off_amount_currency = self.payment_difference
                else:  # if self.payment_type == 'outbound':
                    # Send money.
                    write_off_amount_currency = -self.payment_difference

                payment_vals["write_off_line_vals"].append(
                    {
                        "name": self.writeoff_label,
                        "account_id": self.writeoff_account_id.id,
                        "partner_id": self.partner_id.id,
                        "currency_id": self.currency_id.id,
                        "amount_currency": write_off_amount_currency,
                        "balance": self.currency_id._convert(
                            write_off_amount_currency,
                            self.company_id.currency_id,
                            self.company_id,
                            self.payment_date,
                        ),
                    }
                )
        return payment_vals

    def _create_payment_vals_from_batch(self, batch_result):
        batch_values = self._get_wizard_values_from_batch(batch_result)

        if batch_values["payment_type"] == "inbound":
            partner_bank_id = self.journal_id.bank_account_id.id
        else:
            partner_bank_id = batch_result["payment_values"]["partner_bank_id"]

        payment_method_line = self.payment_method_line_id

        if batch_values["payment_type"] != payment_method_line.payment_type:
            payment_method_line = self.journal_id._get_available_payment_method_lines(
                batch_values["payment_type"]
            )[:1]

        payment_vals = {
            "date": self.payment_date,
            "amount": batch_values["source_amount_currency"],
            "payment_type": batch_values["payment_type"],
            "partner_type": batch_values["partner_type"],
            "ref": self._get_batch_communication(batch_result),
            "journal_id": self.journal_id.id,
            "company_id": self.company_id.id,
            "currency_id": batch_values["source_currency_id"],
            "partner_id": batch_values["partner_id"],
            "partner_bank_id": partner_bank_id,
            "payment_method_line_id": payment_method_line.id,
            "destination_account_id": batch_result["lines"][0].account_id.id,
            "write_off_line_vals": [],
        }

        total_amount, mode = self._get_total_amount_using_same_currency(batch_result)
        currency = self.env["res.currency"].browse(batch_values["source_currency_id"])
        if mode == "early_payment":
            keep_open_for_early_payment_discount = self.keep_apply_discount_early
            payment_vals["amount"] = total_amount

            epd_aml_values_list = []
            for aml in batch_result["lines"]:
                if (
                    aml.move_id._is_eligible_for_early_payment_discount(
                        currency, self.payment_date
                    )
                    or keep_open_for_early_payment_discount
                ):
                    epd_aml_values_list.append(
                        {
                            "aml": aml,
                            "amount_currency": -aml.amount_residual_currency,
                            "balance": currency._convert(
                                -aml.amount_residual_currency,
                                aml.company_currency_id,
                                self.company_id,
                                self.payment_date,
                            ),
                        }
                    )

            open_amount_currency = (
                batch_values["source_amount_currency"] - total_amount
            ) * (-1 if batch_values["payment_type"] == "outbound" else 1)
            open_balance = currency._convert(
                open_amount_currency,
                aml.company_currency_id,
                self.company_id,
                self.payment_date,
            )
            early_payment_values = self.env[
                "account.move"
            ]._get_invoice_counterpart_amls_for_early_payment_discount(
                epd_aml_values_list, open_balance
            )
            for aml_values_list in early_payment_values.values():
                payment_vals["write_off_line_vals"] += aml_values_list

        return payment_vals
