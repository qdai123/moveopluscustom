# -*- coding: utf-8 -*-
from odoo import models, fields


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    # helpdesk_ticket_stock_move_line_ids = fields.Many2many()
