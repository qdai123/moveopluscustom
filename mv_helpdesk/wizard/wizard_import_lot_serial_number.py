# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class WizardImportLotSerialNumber(models.TransientModel):
    _name = _description = "wizard.import.lot.serial.number"

    helpdesk_ticket_id = fields.Many2one(comodel_name="helpdesk.ticket", readonly=True)
    portal_lot_serial_number = fields.Text(string="Input Lot/Serial Number or QR-Code")

    def action_import(self):
        codes = self.portal_lot_serial_number
        if codes:
            codes_data = self._get_codes_format(codes)
            messages_list = self._get_message_data(codes_data)
            error_messages = [
                message[1]
                for message in messages_list
                if message[0]
                in ["is_empty", "code_not_found", "code_already_registered"]
            ]

            if error_messages:
                raise ValidationError("\n".join(error_messages))

        ticket = self.helpdesk_ticket_id
        if ticket.action_scan_lot_serial_number(self.portal_lot_serial_number):
            ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
            move_line_env = self.env["stock.move.line"]

            formatted_codes = self._get_codes_format(codes)
            messages_list = self._get_message_data(formatted_codes)
            stock_move_line_ids = [
                move_line[0]
                for move_line in messages_list
                if isinstance(move_line[0], int)
            ]

            stock_move_lines = move_line_env.browse(stock_move_line_ids)
            existing_ticket_move_lines = ticket_product_moves_env.search(
                [
                    ("stock_move_line_id", "in", stock_move_line_ids),
                    ("helpdesk_ticket_id", "=", False),
                ]
            )

            existing_ticket_move_lines.sudo().unlink()

            new_entries = [
                {"stock_move_line_id": move_line.id, "helpdesk_ticket_id": ticket.id}
                for move_line in stock_move_lines
            ]

            ticket_product_moves_env.sudo().create(new_entries)

    # =================================
    # HELPER/PRIVATE Methods
    # =================================

    def _get_codes_format(self, codes):
        """
        Return the formatted list of codes.
        :return: []
        """
        return (
            self.env["helpdesk.ticket"].sudo().convert_to_list_codes(codes)
            if codes
            else []
        )

    def _get_message_data(self, codes_data):
        """
        Return the message list of codes.
        :return: []
        """
        return (
            self.env["helpdesk.ticket"]
            .sudo()
            ._validation_portal_lot_serial_number(codes_data)
            if codes_data
            else []
        )
