# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    hidden_show_qty = fields.Boolean(
        help="Do not show change qty in website", default=False, copy=False
    )
    discount_line_id = fields.Many2one("mv.compute.discount.line")
    code_product = fields.Char(help="Do not recompute discount")

    # SUPPORT Fields:
    is_sales_manager = fields.Boolean(
        compute="_compute_is_sales_manager",
        default=lambda self: self.env.user.has_group("sales_team.group_sale_manager"),
    )

    @api.depends_context("uid")
    def _compute_is_sales_manager(self):
        is_manager = self.env.user.has_group("sales_team.group_sale_manager")

        for user in self:
            user.is_sales_manager = is_manager

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
        res = super().write(vals)
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

    @api.constrains("product_uom_qty")
    def _check_order_not_free_qty_today(self):
        for so_line in self.filtered(
            lambda line: (line.order_id.state != "draft" or line.state != "draft")
            and line.product_template_id.detailed_type != "service"
        ):
            if so_line.product_uom_qty > so_line.free_qty_today:
                error_message = (
                    "Bạn không được phép đặt quá số lượng hiện tại:"
                    "\n- Sản phẩm: %s"
                    "\n- Số lượng hiện tại: %s Cái"
                    "\n\nVui lòng kiểm tra lại số lượng còn lại trong kho."
                    % (so_line.product_template_id.name, int(so_line.free_qty_today))
                )
                raise ValidationError(error_message)
