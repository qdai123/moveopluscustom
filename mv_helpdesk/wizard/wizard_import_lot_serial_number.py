# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import ValidationError


class WizardImportLotSerialNumber(models.TransientModel):
    _name = _description = "wizard.import.lot.serial.number"

    helpdesk_ticket_id = fields.Many2one(comodel_name="helpdesk.ticket", readonly=True)
    helpdesk_ticket_type_id = fields.Many2one(
        comodel_name="helpdesk.ticket.type", readonly=True
    )
    portal_lot_serial_number = fields.Text(string="Input Lot/Serial Number or QR-Code")

    def action_import(self):
        """
        Import the codes from the portal_lot_serial_number field into the helpdesk_ticket_id.
        If the codes are not provided, raise a ValidationError with a descriptive error message.
        """
        ticket = self.env["helpdesk.ticket"].browse(self.helpdesk_ticket_id.id)
        ticket_type = self.env["helpdesk.ticket.type"].browse(
            self.helpdesk_ticket_type_id.id
        )
        codes = self.portal_lot_serial_number
        if not codes:
            raise ValidationError("Vui lòng nhập mã để quá trình tiếp tục.")

        ticket.sudo()._process_ticket_barcode(ticket, ticket_type, codes)
