# -*- coding: utf-8 -*-
from odoo import fields, models


class HelpdeskTicketType(models.Model):
    _inherit = "helpdesk.ticket.type"

    code = fields.Char(size=64, index=True, help="Helps clearly identify ticket type")
