# -*- coding: utf-8 -*-
from odoo import fields, models
from odoo.exceptions import ValidationError


class WizardImportLotSerialNumber(models.TransientModel):
    _name = "wizard.import.lot.serial.number"
    _description = "Wizard to import Lot/Serial Number or QR-Code"

    helpdesk_ticket_id = fields.Many2one("helpdesk.ticket", readonly=True)
    helpdesk_ticket_type_id = fields.Many2one("helpdesk.ticket.type", readonly=True)
    portal_lot_serial_number = fields.Text()

    def action_import(self):
        """
        Import the codes from the portal_lot_serial_number field into the helpdesk_ticket_id.
        If the codes are not provided, raise a ValidationError with a descriptive error message.
        """
        if not self.portal_lot_serial_number:
            raise ValidationError("Vui lòng nhập mã để quá trình tiếp tục.")

        self.helpdesk_ticket_id._process_ticket_product_moves(
            self.helpdesk_ticket_id,
            self.helpdesk_ticket_type_id,
            self.portal_lot_serial_number,
        )
