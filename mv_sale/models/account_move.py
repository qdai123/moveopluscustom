# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        # Gather all unique invoice origins
        invoice_origins = {move.invoice_origin for move in self if move.invoice_origin}

        if invoice_origins:
            # Search for orders with those invoice origins
            orders = self.env["sale.order"].search(
                [("name", "in", list(invoice_origins))]
            )

            for invoice_origin in invoice_origins:
                # Filter orders by invoice origin and lack of date_invoice
                orders_to_update = orders.filtered(
                    lambda so: so.name == invoice_origin and not so.date_invoice
                )
                if orders_to_update:
                    date_invoice = self.filtered(
                        lambda m: m.invoice_origin == invoice_origin
                    ).mapped("date_invoice")
                    # Assuming all moves with the same invoice_origin have the same date_invoice
                    if date_invoice:
                        orders_to_update.write({"date_invoice": date_invoice[0]})

        return super().action_post()
