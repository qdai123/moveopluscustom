# -*- coding: utf-8 -*-
from odoo.addons.mv_sale.models.sale_order import GROUP_SALES_MANAGER

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # === Permission/Flags Fields ===#
    is_sales_manager = fields.Boolean(compute="_compute_permissions")

    @api.depends_context("uid")
    def _compute_permissions(self):
        for record in self:
            record.is_sales_manager = self.env.user.has_group(GROUP_SALES_MANAGER)

    # ================================================== #

    code_product = fields.Char(help="Do not recompute discount")
    hidden_show_qty = fields.Boolean(help="Don't show change Quantity on Website")
    price_subtotal_before_discount = fields.Monetary(
        compute="_compute_price_subtotal_before_discount",
        store=True,
        string="Price Subtotal before Discount",
        currency_field="currency_id",
    )

    # === Discount Agency ===#
    discount_line_id = fields.Many2one(comodel_name="mv.compute.discount.line")
    is_discount_agency = fields.Boolean(string="Is a Discount Agency", default=False)
    recompute_discount_agency = fields.Boolean(
        related="order_id.recompute_discount_agency"
    )

    def _is_not_sellable_line(self):
        return self.hidden_show_qty or super()._is_not_sellable_line()

    def _filter_discount_agency_lines(self, order=False):
        # Return an empty recordset if no order_id is provided
        if not order:
            return self.browse()

        # Filter the order lines based on the conditions
        discount_agency_lines = order.order_line.filtered(
            lambda sol: sol.product_id.default_code == "CKT"
            and sol.product_id.product_tmpl_id.detailed_type == "service"
        )

        return discount_agency_lines

    @api.depends("price_unit", "qty_delivered", "discount")
    def _compute_price_subtotal_before_discount(self):
        for o_line in self:
            if o_line.price_unit and o_line.qty_delivered and o_line.discount:
                order_line.price_subtotal_before_discount = (
                    o_line.price_unit * o_line.qty_delivered
                ) - ((o_line.price_unit * o_line.qty_delivered) * o_line.discount / 100)
            else:
                o_line.price_subtotal_before_discount = 0

    @api.depends("state")
    def _compute_product_uom_readonly(self):
        # OVERRIDE to set access groups of Sales
        for line in self:
            # line.ids checks whether it's a new record not yet saved
            line.product_uom_readonly = (
                line.ids
                and line.state in ["sale", "cancel"]
                or (
                    not line.is_sales_manager
                    and line.product_template_id.detailed_type == "service"
                )
            )

    @api.depends("state", "product_id", "qty_delivered", "qty_invoiced")
    def _compute_product_updatable(self):
        # OVERRIDE to set access groups of Sales
        for line in self:
            if line.state == "cancel":
                line.product_updatable = False
            elif line.state == "sale" and (
                line.order_id.locked or line.qty_invoiced > 0 or line.qty_delivered > 0
            ):
                line.product_updatable = False
            elif (
                line.state not in ["cancel", "sale"]
                and not line.is_sales_manager
                and line.product_type == "service"
            ):
                line.product_updatable = True
            else:
                line.product_updatable = True

    def write(self, vals):
        OrderLines = super(SaleOrderLine, self).write(vals)

        for o_line in self:
            if o_line.hidden_show_qty or o_line.reward_id:
                return OrderLines
            else:
                # [!] Khi có sự thay đổi về số lượng cần tính toán lại các dòng chiết khấu
                if "product_uom_qty" in vals and vals.get("product_uom_qty"):
                    o_line.order_id.action_clear_discount_lines()

        return OrderLines

    def unlink(self):
        for o_line in self:
            if (
                o_line.product_id
                and o_line.product_id.default_code
                and "Delivery_" not in o_line.product_id.default_code
            ):
                order = o_line.order_id
                order._compute_bonus()

        return super(SaleOrderLine, self).unlink()
