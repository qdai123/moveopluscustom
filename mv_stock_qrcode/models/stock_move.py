# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StockMove(models.Model):
    _inherit = "stock.move"

    base_qrcode = fields.Char(
        compute="_compute_base_qrcode",
        string="QR-Code based",
    )
    number_qrcode_input_limited = fields.Integer(
        default=0,
        compute="_compute_number_qrcode_input_limited",
        string="Limited number of QR-Codes to generate",
        help="Compare with Product Demand must be the same or less than with demand of Product",
    )

    # INHERIT Fields:
    number_start = fields.Integer(
        default=1,
        compute="_auto_get_number_start",
        help="Find the next Number Start by Picking, Product and Week Number",
    )

    @api.depends("product_id", "inventory_period_id")
    def _auto_get_number_start(self):
        for move in self:
            if not move.move_line_ids or not move.inventory_period_id:
                move.number_start = 1
            else:
                if move and move.product_id and move.inventory_period_id:
                    product = (
                        self.env["product.product"].browse(move.product_id.id) or False
                    )
                    inv_period = (
                        self.env["inventory.period"].browse(move.inventory_period_id.id)
                        or False
                    )
                    week_number = inv_period
                    next_number_to_generate = self._get_next_number_start(
                        product, week_number
                    ) or 1
                    move.number_start = next_number_to_generate

    @api.depends("move_line_ids")
    def _compute_number_qrcode_input_limited(self):
        for move in self:
            if move.move_line_ids:
                current_reserved = sum(move.move_line_ids.mapped("quantity")) or 0
                move.number_qrcode_input_limited = max(
                    0, move.product_uom_qty - current_reserved
                )
            else:
                move.number_qrcode_input_limited = move.product_uom_qty

    @api.depends("product_id", "inventory_period_id")
    def _compute_base_qrcode(self):
        for move in self:
            if move.product_id and move.inventory_period_id:
                move.base_qrcode = "{week_number}{product_barcode}".format(
                    week_number=move.inventory_period_id.week_number_str,
                    product_barcode=move.product_id.barcode,
                )
            else:
                move.base_qrcode = "PRODUCT_BARCODE_"

    # ===============================
    # ORM Methods
    # ===============================

    @api.model_create_multi
    def create(self, vals_list):
        print(f"Create Move: {vals_list}")
        return super(StockMove, self).create(vals_list)

    def write(self, vals):
        print(f"Write Picking: {vals}")
        return super(StockMove, self).write(vals)

    # ===============================
    # HELPER Methods
    # ===============================

    def reset_data(self, data={}):
        self.ensure_one()
        self._auto_get_number_start()
        self.write({"number_qrcode": 0})

    def _get_next_number_start(self, product=False, week_number=False):
        if not product:
            raise ValidationError(_("Product not found!"))
        elif not week_number:
            raise ValidationError(_("Week Number is not empty!"))

        self._cr.execute(
            """
            SELECT sml.picking_id,
                       sml.move_id,
                       sml.lot_id,
                       sml.lot_name,
                       pp.id                                             AS product_id,
                       pp.barcode                                   AS product_barcode,
                       sml.inventory_period_name          AS week_number,
                       sml.qr_code,
                       sml.quantity
                FROM stock_move_line sml
                         JOIN product_product pp ON pp.id = sml.product_id
                         JOIN product_template pt ON pt.id = pp.product_tmpl_id AND pt.detailed_type = 'product'
                WHERE sml.product_id = %s
                  AND sml.inventory_period_id = %s
                GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9;
        """
            % (product.id, week_number.id)
        )
        move_line_ids = [
            {
                "week_number": line.get("week_number"),
                "product_id": line.get("product_id"),
                "product_barcode": line.get("product_barcode"),
                "lot_serial_number": line.get("lot_name"),
                "stock_qrcode": line.get("qr_code"),
                "stock_quantity": line.get("quantity"),
            }
            for line in self._cr.dictfetchall()
        ]
        if move_line_ids:
            return len(move_line_ids) + 1
        else:
            return len(move_line_ids)

    def _get_next_unique_qr_code(self, next_unique):
        while True:
            code_prefix = self.base_qrcode
            code_suffix = str(next_unique).zfill(5)
            qrcode = "{prefix}{suffix}".format(prefix=code_prefix, suffix=code_suffix)
            move_line_exist = self.env["stock.move.line"].search(
                [
                    ("product_id", "=", self.product_id.id),
                    ("inventory_period_id", "=", self.inventory_period_id.id),
                    ("qr_code_prefix", "=", code_prefix),
                    ("qr_code_suffix", "=", code_suffix),
                ],
                limit=1,
            )

            if not move_line_exist:
                return 1, qrcode, code_prefix, code_suffix

            next_unique += 1

    def _add_qrcode_move_line_to_vals_list(self, start, number_to_generate):
        return [
            self._prepare_move_line_vals_for_qrcode(
                *self._get_next_unique_qr_code(start + num)
            )
            for num in range(int(number_to_generate))
        ]

    def _prepare_move_line_vals_for_qrcode(
        self, quantity, qr_code, qr_code_prefix, qr_code_suffix
    ):
        self.ensure_one()
        vals = {
            "move_id": self.id,
            "product_id": self.product_id.id,
            "product_uom_id": self.product_uom.id,
            "location_id": self.location_id.id,
            "location_dest_id": self.location_dest_id.id,
            "picking_id": self.picking_id.id,
            "company_id": self.company_id.id,
            "inventory_period_id": self.inventory_period_id.id,
        }
        if qr_code and qr_code_prefix and qr_code_suffix:
            vals = dict(
                vals,
                is_specify_qrcode=True,
                qr_code_prefix=qr_code_prefix,
                qr_code_suffix=qr_code_suffix,
                qr_code=qr_code,
                quantity=quantity,
            )
        return vals

    # ===============================
    # ACTION Methods
    # ===============================

    def action_specify_qrcode(self):
        """MOVEOPLUS Override"""

        picking = self.picking_id or False
        if picking and picking.move_line_ids_without_package:
            remove_lines = picking.move_line_ids_without_package.filtered(
                lambda line: not line.qr_code and line.move_id == self
            )
            remove_lines.unlink()

        week_number = self.inventory_period_id or False
        if not week_number:
            raise UserError(_("Please choose the Week Number!"))

        product_demand = self.product_uom_qty
        number_of_qrcode_input = self.number_qrcode or 0
        number_of_qrcode_input_limited = self.number_qrcode_input_limited
        if number_of_qrcode_input == 0:
            raise UserError(_("Number of QR-Code to generate must be greater than 0!"))
        elif product_demand < number_of_qrcode_input:
            raise UserError(
                _("Number of QR-Code cannot greater than demand of Product!")
            )

        if number_of_qrcode_input > number_of_qrcode_input_limited:
            raise UserError(
                _(
                    "Please enter Number of QR-Code less than or equal to available that can be generated!"
                )
            )

        current_reserved = sum(self.move_line_ids.mapped("quantity"))
        available_quantity = max(0, int(product_demand) - int(current_reserved))

        number_generate = min(available_quantity, number_of_qrcode_input)
        if number_generate <= 0:
            return

        vals_list = self._add_qrcode_move_line_to_vals_list(
            start=self.number_start, number_to_generate=number_generate
        )
        if vals_list:
            self.env["stock.move.line"].with_context(qrcode_generate=True).create(
                vals_list
            )

        # RESET Data
        self.reset_data()

    def action_remove_all(self):
        return super(StockMove, self).action_remove_all()

    # ===============================
    # CONSTRAINS Methods
    # ===============================
