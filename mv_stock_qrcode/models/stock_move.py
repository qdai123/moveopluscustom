# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError


class StockMove(models.Model):
    _inherit = "stock.move"

    number_start = fields.Integer(compute="_compute_auto_call_next_number", store=True)
    numer_limit_can_be_generate = fields.Integer(
        compute="_compute_auto_call_next_number",
        string="Available can be Generate",
        store=True,
        readonly=True,
    )

    @api.depends("move_line_ids")
    def _compute_auto_call_next_number(self):
        for move in self:
            if not move.move_line_ids:
                move.number_start = 1
                move.numer_limit_can_be_generate = move.product_uom_qty
            else:
                move.number_start = self._get_next_number_start(move) + 1
                if move.number_start > move.product_uom_qty:
                    move.number_start = 0
                current_reserved = sum(move.move_line_ids.mapped("quantity"))
                available_quantity = max(0, move.product_uom_qty - current_reserved)
                move.numer_limit_can_be_generate = available_quantity

    @api.constrains("product_uom_qty", "number_qrcode")
    def _validate_not_over_product_demand(self):
        for rec in self:
            if rec.product_uom_qty and rec.number_qrcode and rec.number_qrcode > int(rec.product_uom_qty):
                raise UserError(_("QR Code Number cannot over Product Demand!"))

    def _generate_qrcode(self, qrcode, next_number):
        updated_code = f"{qrcode}{str(next_number).zfill(5)}"
        return updated_code

    def _get_next_number_start(self, stock_move):
        if not stock_move:
            raise ValidationError(_("Stock Move not found!"))

        self._cr.execute("SELECT MAX(number_call) FROM stock_move_line WHERE move_id = %s;" % stock_move.id)
        res = self._cr.fetchone()
        return res[0] if res else 0

    def _get_next_unique_qr_code(self, next_number):
        while True:
            qrcode = '%s%s' % (self.inventory_period_id.week_number_str or '', self.product_id.barcode or '')
            qr_code_format = self._generate_qrcode(qrcode, next_number)
            sml = self.env["stock.move.line"].search([
                ("qr_code", "=", qr_code_format),
                ("number_call", "=", next_number)
            ], limit=1)

            if not sml:
                return qr_code_format, next_number

            next_number += 1

    def _prepare_sml_vals(self, qr_code, number_call):
        return {
            'product_id': self.product_id.id,
            'picking_id': self.picking_id.id,
            'product_uom_id': self.product_uom.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'inventory_period_id': self.inventory_period_id and self.inventory_period_id.id or False,
            'is_specify_qrcode': True,
            'qr_code': qr_code,
            'number_call': number_call,
            'quantity': 1
        }

    def action_specify_qrcode(self):
        if not self.inventory_period_id:
            raise ValidationError(_("Please enter the Week Number!"))

        if not self.number_qrcode:
            raise ValidationError(_("Please enter the QR-Code Number!"))

        if (self.numer_limit_can_be_generate
                and self.number_qrcode
                and self.number_qrcode > self.numer_limit_can_be_generate):
            raise UserError(_("Please enter QR-Code Number less than or equal to available can be generate!"))

        if self.picking_id and self.picking_id.move_line_ids_without_package:
            remove_lines = (
                self.picking_id.move_line_ids_without_package.filtered(
                    lambda line: not line.qr_code and line.move_id == self
                )
            )
            remove_lines.unlink()

        current_reserved = sum(self.move_line_ids.mapped("quantity"))
        available_quantity = max(0, int(self.product_uom_qty) - int(current_reserved))
        number_generate = min(available_quantity, self.number_qrcode)

        if number_generate <= 0:
            self.write({"number_qrcode": 0})
            return

        next_number = self.number_start or 1
        sml_vals_lst = [
            self._prepare_sml_vals(
                *self._get_next_unique_qr_code(next_number + i)
            ) for i in range(number_generate)
        ]
        if sml_vals_lst:
            self.with_context(create_qrcode=True).move_line_ids = [
                (0, 0, sml_vals)
                for sml_vals in sml_vals_lst
            ]
