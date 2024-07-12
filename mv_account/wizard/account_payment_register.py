# -*- coding: utf-8 -*-
from odoo import models


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    # /// MOVEOPLUS OVERRIDE ///

    def _get_total_amount_using_same_currency(
        self, batch_result, early_payment_discount=True
    ):
        self.ensure_one()
        amount = 0.0
        mode = False
        moves = batch_result["lines"].mapped("move_id")
        for move in moves:
            # MOVEOPLUS OVERRIDE: Check Payment State in ['not_paid', 'partial'] for Early Payment Discount
            for_payment_state_unpaid = move._is_eligible_for_early_payment_discount(
                move.currency_id, self.payment_date
            )
            for_payment_state_partial = (
                move._is_eligible_for_early_payment_discount_partial(
                    move.currency_id, self.payment_date
                )
            )
            if early_payment_discount and (
                for_payment_state_unpaid or for_payment_state_partial
            ):
                amount += move.invoice_payment_term_id._get_amount_due_after_discount(
                    (
                        move.amount_total
                        if for_payment_state_unpaid
                        else move.amount_residual
                    ),
                    move.amount_tax,
                )
                mode = "early_payment"
            else:
                for aml in batch_result["lines"].filtered(
                    lambda line: line.move_id.id == move.id
                ):
                    amount += aml.amount_residual_currency
        return abs(amount), mode

    # -------------------------------------------------------------------------
    # BUSINESS METHODS (OVERRIDE)
    # -------------------------------------------------------------------------

    def _create_payment_vals_from_wizard(self, batch_result):
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
                    # MOVEOPLUS OVERRIDE: Check Payment State in ['not_paid', 'partial'] for Early Payment Discount
                    for_payment_state_unpaid = (
                        aml.move_id._is_eligible_for_early_payment_discount(
                            self.currency_id, self.payment_date
                        )
                    )
                    for_payment_state_partial = (
                        aml.move_id._is_eligible_for_early_payment_discount_partial(
                            self.currency_id, self.payment_date
                        )
                    )
                    if for_payment_state_unpaid or for_payment_state_partial:
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
            payment_vals["amount"] = total_amount

            epd_aml_values_list = []
            for aml in batch_result["lines"]:
                # MOVEOPLUS OVERRIDE: Check Payment State in ['not_paid', 'partial'] for Early Payment Discount
                for_payment_state_unpaid = (
                    aml.move_id._is_eligible_for_early_payment_discount(
                        currency, self.payment_date
                    )
                )
                for_payment_state_partial = (
                    aml.move_id._is_eligible_for_early_payment_discount_partial(
                        currency, self.payment_date
                    )
                )
                if for_payment_state_unpaid or for_payment_state_partial:
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
