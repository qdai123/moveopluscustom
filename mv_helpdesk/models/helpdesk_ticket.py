# -*- coding: utf-8 -*-
from datetime import datetime

from odoo import api, models, fields


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    helpdesk_ticket_product_move_ids = fields.One2many(
        comodel_name='helpdesk.ticket.product.moves',
        inverse_name='helpdesk_ticket_id',
        string="Lot/Serial Number",
    )
    sub_dealer_name = fields.Char(string="Sub-Dealer")
    is_sub_dealer = fields.Boolean(compute='_compute_partner_ticket_type', store=True)
    license_plates = fields.Char(string="License plates")
    mileage = fields.Float(digits=(16, 4), default=0, string="Mileage (Km)")
    is_end_user = fields.Boolean(compute='_compute_partner_ticket_type', store=True)

    # INHERIT Fields:
    name = fields.Char(compute='_compute_partner_ticket_type', store=True, readonly=False, required=False)

    @api.depends("partner_id", "ticket_type_id")
    def _compute_partner_ticket_type(self):
        for rec in self:
            if rec.partner_id and rec.ticket_type_id:
                rec.name = "{}/{}/{}".format(
                    rec.partner_id.name.upper() if rec.partner_id else "-",
                    rec.ticket_type_id.name,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )
                rec.is_sub_dealer = (rec.ticket_type_id
                                     and rec.ticket_type_id.name == 'Kích Hoạt Bảo Hành Lốp Xe Continental (Sub)')
                rec.is_end_user = (rec.ticket_type_id
                                   and
                                   rec.ticket_type_id.name == 'Kích Hoạt Bảo Hành Lốp Xe Continental (Người dùng cuối)')

    @api.model
    def create(self, vals):
        return super(HelpdeskTicket, self).create(vals)

    def write(self, vals):
        res = super(HelpdeskTicket, self).write(vals)
        return res
