# -*- coding: utf-8 -*-
from odoo.addons.mv_sale.models.sale_order import GROUP_SALES_MANAGER

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    # ACCESS/RULE Fields:
    is_sales_manager = fields.Boolean(compute="_compute_permissions")

    @api.depends_context("uid")
    def _compute_permissions(self):
        is_manager = self.env.user.has_group(GROUP_SALES_MANAGER)
        for record in self:
            record.is_sales_manager = is_manager

    # ================================================== #

    hidden_show_qty = fields.Boolean(
        help="Do not show change qty in website", default=False, copy=False
    )
    discount_line_id = fields.Many2one("mv.compute.discount.line")
    code_product = fields.Char(help="Do not recompute discount")
    price_subtotal_before_discount = fields.Monetary(
        "Price sub-total before discount",
        currency_field="currency_id",
        compute="_compute_price_subtotal_before_discount",
        store=True,
    )

    @api.depends("price_unit", "qty_delivered")
    def _compute_price_subtotal_before_discount(self):
        for order_line in self:
            if order_line.price_unit and order_line.qty_delivered:
                total = order_line.price_unit * order_line.qty_delivered
                total_discount = (
                    (order_line.price_unit * order_line.qty_delivered)
                    * order_line.discount
                    / 100
                )
                order_line.price_subtotal_before_discount = total - total_discount
            else:
                order_line.price_subtotal_before_discount = 0

    def _is_not_sellable_line(self):
        return self.hidden_show_qty or super()._is_not_sellable_line()

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

    @api.depends("product_id", "state", "qty_invoiced", "qty_delivered")
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

    def unlink(self):
        for record in self:
            # FIXME: Need to double-check on Workflow of Sales
            # if not record.is_sales_manager and record.product_type == "service":
            #     raise AccessError(_("Bạn không có quyền xoá các loại Sản phẩm thuộc Dịch Vụ. "
            #                         "\nVui lòng liên hệ với Quản trị viên để được hỗ trợ!"))

            if (
                record.product_id
                and record.product_id.default_code
                and record.product_id.default_code.find("Delivery_") > -1
            ):
                pass
            else:
                order_id = record.order_id
                order_id.partner_id.write(
                    {"amount": order_id.partner_id.amount + order_id.bonus_order}
                )
                order_id.write({"bonus_order": 0})
        return super(SaleOrderLine, self).unlink()

    def write(self, vals):
        res = super(SaleOrderLine, self).write(vals)
        for record in self:
            if record.hidden_show_qty or record.reward_id:
                return res
            else:
                order_id = record.order_id
                order_line = order_id.order_line.filtered(
                    lambda x: x.product_id.default_code == "CKT"
                )
                if vals.get("product_uom_qty", False) and len(order_line) > 0:
                    order_line.unlink()
                return res
