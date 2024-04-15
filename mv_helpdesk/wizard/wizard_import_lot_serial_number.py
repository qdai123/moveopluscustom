# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import AccessError, UserError, ValidationError


class WizardImportLotSerialNumber(models.TransientModel):
    _name = _description = "wizard.import.lot.serial.number"

    helpdesk_ticket_id = fields.Many2one(comodel_name="helpdesk.ticket", readonly=True)
    portal_lot_serial_number = fields.Text(string="Input Lot/Serial Number")

    def action_import(self):
        env_call = self.env["helpdesk.ticket"].sudo()
        error_messages = []

        if self.portal_lot_serial_number:
            serial_numbers_fmt_list = env_call._format_portal_lot_serial_number(self.portal_lot_serial_number)
            messages_list = env_call._validation_portal_lot_serial_number(serial_numbers_fmt_list)

            error_messages += [message[1] for message in messages_list if
                               message[0] in ["serial_number_is_empty",
                                              "serial_number_not_found",
                                              "serial_number_already_registered"]]

        if error_messages:
            raise ValidationError('\n'.join(error_messages))
        else:
            ticket = self.helpdesk_ticket_id
            scanning_pass = ticket.action_scan_lot_serial_number(self.portal_lot_serial_number)
            if scanning_pass:
                ticket_product_moves_env = self.env["mv.helpdesk.ticket.product.moves"]
                move_line_env = self.env["stock.move.line"]

                messages_list = ticket._validation_portal_lot_serial_number(
                    ticket._format_portal_lot_serial_number(self.portal_lot_serial_number)
                )
                stock_move_line_ids = [
                    move_line[0] for move_line in messages_list if isinstance(move_line[0], int)
                ]

                for stock_move_line in move_line_env.browse(stock_move_line_ids):
                    ticket_stock_move_line_exist = ticket_product_moves_env.search([
                        ("stock_move_line_id", "=", stock_move_line.id),
                        ("helpdesk_ticket_id", "=", False)
                    ], limit=1)

                    if ticket_stock_move_line_exist:
                        ticket_stock_move_line_exist.sudo().unlink()
                        ticket_product_moves_env.sudo().create({
                            "stock_move_line_id": stock_move_line.id,
                            "helpdesk_ticket_id": ticket.id
                        })
                    else:
                        ticket_product_moves_env.sudo().create({
                            "stock_move_line_id": stock_move_line.id,
                            "helpdesk_ticket_id": ticket.id
                        })
