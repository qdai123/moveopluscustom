# -*- coding: utf-8 -*-
import logging
from datetime import datetime

from odoo import api, models, fields
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    helpdesk_ticket_product_move_ids = fields.One2many(
        comodel_name='mv.helpdesk.ticket.product.moves',
        inverse_name='helpdesk_ticket_id',
        string="Lot/Serial Number",
    )
    sub_dealer_name = fields.Char(string="Sub-Dealer")
    is_sub_dealer = fields.Boolean(compute='_compute_ticket_type')
    license_plates = fields.Char(string="License plates")
    mileage = fields.Float(digits=(16, 4), default=0, string="Mileage (Km)")
    is_end_user = fields.Boolean(compute='_compute_ticket_type')
    portal_lot_serial_number = fields.Text()
    messages_label_info = fields.Html()

    # INHERIT Fields:
    name = fields.Char(compute='_compute_name', store=True, readonly=False, required=False, tracking=False)

    @api.depends("partner_id", "ticket_type_id")
    def _compute_name(self):
        for rec in self:
            if rec.partner_id and rec.ticket_type_id:
                rec.name = "{}/{}/{}".format(
                    rec.partner_id.name.upper() if rec.partner_id else "-",
                    rec.ticket_type_id.name,
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                )

    @api.depends("ticket_type_id")
    def _compute_ticket_type(self):
        for rec in self:
            rec.is_sub_dealer = False
            rec.is_end_user = False
            if (rec.ticket_type_id
                    and rec.ticket_type_id.name == 'Kích Hoạt Bảo Hành Lốp Xe Continental (Sub)'):
                rec.is_sub_dealer = True
                rec.is_end_user = False
            elif (rec.ticket_type_id
                  and rec.ticket_type_id.name == 'Kích Hoạt Bảo Hành Lốp Xe Continental (Người dùng cuối)'):
                rec.is_end_user = True
                rec.is_sub_dealer = False

    @api.model
    def create(self, vals):

        if "portal_lot_serial_number" in vals and vals.get("portal_lot_serial_number"):
            messages_list = self._validation_portal_lot_serial_number(text=vals["portal_lot_serial_number"])
            for message in messages_list:
                if message[0] == "ERROR":
                    raise ValidationError(message[1])

            translation_table = str.maketrans('', '', '.,')
            text = vals["portal_lot_serial_number"]
            serial_number_list = [
                str(serial_num).strip().translate(translation_table) for serial_num in text.split(',')
            ]
            lot_serial_number_in_stock = (
                self.env["mv.helpdesk.ticket.product.moves"].search([
                    ("parent_id", "=", False),
                    ("lot_name", "in", serial_number_list)
                ])
            )
            for lot_serial_number in lot_serial_number_in_stock:
                self.env["mv.helpdesk.ticket.product.moves"].create({
                    "parent_id": lot_serial_number.id,
                    "stock_move_line_id": lot_serial_number.stock_move_line_id.id,
                    "helpdesk_ticket_id": self.id
                })

        res = super(HelpdeskTicket, self).create(vals)
        res._compute_name()
        return res

    def write(self, vals):

        if "portal_lot_serial_number" in vals and vals.get("portal_lot_serial_number"):
            messages_list = self._validation_portal_lot_serial_number(text=vals["portal_lot_serial_number"])
            for message in messages_list:
                if message[0] == "ERROR":
                    raise ValidationError(message[1])

            translation_table = str.maketrans('', '', '.,')
            text = vals["portal_lot_serial_number"]
            serial_number_list = [
                str(serial_num).strip().translate(translation_table) for serial_num in text.split(',')
            ]
            lot_serial_number_in_stock = (
                self.env["mv.helpdesk.ticket.product.moves"].search([
                    ("parent_id", "=", False),
                    ("lot_name", "in", serial_number_list)
                ])
            )
            for lot_serial_number in lot_serial_number_in_stock:
                self.env["mv.helpdesk.ticket.product.moves"].create({
                    "parent_id": lot_serial_number.id,
                    "stock_move_line_id": lot_serial_number.stock_move_line_id.id,
                    "helpdesk_ticket_id": self.id
                })

        return super(HelpdeskTicket, self).write(vals)

    def action_validate_portal_lot_serial_number(self):
        # messages_html = """<div>"""
        messages_list = self._validation_portal_lot_serial_number(text=self.portal_lot_serial_number)
        for message in messages_list:
            if message[0] == "ERROR":
                raise ValidationError(message[1])
                # messages_html += '<span style="color: #E4080A;">' + message[1] + '</span>'

            # if message[0] == "PASS":
            #     messages_html += '<span style="color: #40DE12;">' + message[1] + '</span>'

        # messages_html += """<div>"""
        # return self.write({"messages_label_info": messages_html})
        return True

    def _validation_portal_lot_serial_number(self, text=None):
        messages_list = []
        if text:
            lot_serial_number_in_stock = self.env["mv.helpdesk.ticket.product.moves"].search([("lot_name", "!=", "")])
            translation_table = str.maketrans('', '', '.,')
            serial_number_list = [
                str(serial_num).strip().translate(translation_table) for serial_num in text.split(',')
            ]
            for serial_number in serial_number_list:
                if serial_number not in lot_serial_number_in_stock.mapped("lot_name"):
                    messages_list.append(("ERROR",
                                          "Mã %s không tồn tại trên hệ thống hoặc chưa cập nhât, "
                                          "vui lòng kiểm tra lại."
                                          % serial_number
                                          ))

                if lot_serial_number_in_stock.filtered(
                        lambda r: r.parent_id
                                  and r.helpdesk_ticket_id
                                  and r.lot_name == serial_number or r.name == serial_number
                ).helpdesk_ticket_id:
                    messages_list.append(("ERROR", "Mã %s đã trùng với Ticket khác." % serial_number))
                else:
                    for rec in lot_serial_number_in_stock:
                        if serial_number == rec.lot_name:
                            messages_list.append(("PASS",
                                                  "%s - %s"
                                                  % (serial_number,
                                                     rec.product_id.name if rec.product_id else "<Product not found>")
                                                  ))

        return messages_list
