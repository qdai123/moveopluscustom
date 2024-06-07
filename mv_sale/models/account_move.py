# -*- coding: utf-8 -*-
from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_post(self):
        """
        Overrides the action_post method from the [account.move] model.
        This method is called when an invoice is validated.
        If the invoice has an origin (i.e., it was created from a sales order),
        it updates the "date_invoice" field of the corresponding sales order with the current date.
        """
        for record in self:
            # Check if the invoice has an origin
            if record.invoice_origin not in ("", False):
                # Search for the sales order that matches the invoice origin
                order_id = self.env["sale.order"].search(
                    [("name", "=", record.invoice_origin)]
                )

                # Check if a matching sales order was found
                if len(order_id) > 0:
                    # Check if the sales order does not already have a "date_invoice"
                    if not order_id.date_invoice:
                        # Update the "date_invoice" field of the sales order with the current date
                        order_id.write({"date_invoice": fields.datetime.now()})

        # Call the parent method
        return super().action_post()
