# -*- coding: utf-8 -*-
import logging

from odoo.addons.mv_sale.models.sale_order import GROUP_SALES_MANAGER

from odoo import api, fields, models
from odoo.tools.sql import column_exists, create_column

_logger = logging.getLogger(__name__)


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
    discount_line_id = fields.Many2one("mv.compute.discount.line")
    is_discount_agency = fields.Boolean(
        "Is a Discount Agency",
        compute="_compute_is_discount_agency",
        store=True,
        compute_sudo=True,
    )
    recompute_discount_agency = fields.Boolean(
        related="order_id.recompute_discount_agency"
    )

    # === OVERRIDE METHODS ===#

    def _auto_init(self):
        # MOVEO+ OVERRIDE: Create column to stop ORM from computing it himself (too slow)
        if not column_exists(self.env.cr, "sale_order_line", "is_discount_agency"):
            create_column(self.env.cr, "sale_order_line", "is_discount_agency", "bool")
            self.env.cr.execute(
                """
                UPDATE sale_order_line line
                SET is_discount_agency = (pt.type = 'service' AND pp.default_code = 'CKT')
                FROM product_product pp
                LEFT JOIN product_template pt ON pt.id = pp.product_tmpl_id
                WHERE pp.id = line.product_id
            """
            )
        return super()._auto_init()

    # /// ORM Methods

    def _compute_product_uom_readonly(self):
        # MOVEO+ OVERRIDE: TODO <Update Description>
        for so_line in self:
            so_line.product_uom_readonly = (
                so_line.ids
                and so_line.state in ["sale", "cancel"]
                or (
                    not so_line.is_sales_manager
                    and so_line.product_template_id.detailed_type == "service"
                )
            )

    def _compute_product_updatable(self):
        # MOVEO+ OVERRIDE: TODO <Update Description>
        for so_line in self:
            if so_line.state == "cancel":
                so_line.product_updatable = False
            elif so_line.state == "sale" and (
                so_line.order_id.locked
                or so_line.qty_invoiced > 0
                or so_line.qty_delivered > 0
            ):
                so_line.product_updatable = False
            elif (
                so_line.state not in ["cancel", "sale"]
                and not so_line.is_sales_manager
                and so_line.product_type == "service"
            ):
                so_line.product_updatable = True
            else:
                so_line.product_updatable = True

    # /// CRUD Methods

    def write(self, vals):
        OrderLines = super(SaleOrderLine, self).write(vals)

        for so_line in self:
            if so_line.hidden_show_qty or so_line.reward_id:
                return OrderLines
            else:
                # [!] Khi có sự thay đổi về số lượng cần tính toán lại các dòng chiết khấu
                if "product_uom_qty" in vals and vals.get("product_uom_qty"):
                    so_line.order_id.action_clear_discount_lines()

        return OrderLines

    def unlink(self):
        for so_line in self:
            if (
                so_line.product_id
                and so_line.product_id.default_code
                and "Delivery_" not in so_line.product_id.default_code
            ):
                order = so_line.order_id
                order._compute_partner_bonus()
                order._compute_bonus_order_line()

        return super(SaleOrderLine, self).unlink()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        # MOVEO+ OVERRIDE: Force to delete the record if it's not confirmed by Sales Manager
        if not self.env.user.has_group(GROUP_SALES_MANAGER):
            return super(SaleOrderLine, self)._unlink_except_confirmed()

    # /// HOOKS Methods

    def _is_not_sellable_line(self):
        # MOVEO+ OVERRIDE: TODO <Update Description>
        return self.hidden_show_qty or super()._is_not_sellable_line()

    # === MOVEOPLUS METHODS ===#

    def _filter_discount_agency_lines(self, order=False):
        """
            Tìm kiếm các dòng có tính chiết khấu sản lượng (Tháng/Quý/Năm) của Đại lý
        :param order: Base on sale.order recordset
        :return: sale.order.line recordset
        """
        try:
            # [>] Ensure that the method is called on a single record
            # self.ensure_one()

            # [>] Return an empty recordset if no order_id is provided
            if not order:
                return self.browse()

            # [>] Filter the order lines based on the conditions
            # [1] The product is a service
            # [2] The product is a service with default code "CKT"
            agency_order_lines = order.order_line.filtered(
                lambda sol: sol.product_id.product_tmpl_id.detailed_type == "service"
                and sol.product_id.default_code == "CKT"
            )
            return agency_order_lines
        except Exception as e:
            _logger.error(f"Failed to filter agency order lines: {e}")
            return self.env["sale.order.line"]

    # /// ORM Methods

    @api.depends("product_id.product_tmpl_id.detailed_type", "product_id.default_code")
    def _compute_is_discount_agency(self):
        for so_line in self:
            so_line.is_discount_agency = so_line._filter_discount_agency_lines(
                so_line.order_id
            )

    @api.depends("price_unit", "qty_delivered", "discount")
    def _compute_price_subtotal_before_discount(self):
        for so_line in self:
            if so_line.price_unit and so_line.qty_delivered and so_line.discount:
                so_line.price_subtotal_before_discount = (
                    so_line.price_unit * so_line.qty_delivered
                ) - (
                    (so_line.price_unit * so_line.qty_delivered)
                    * so_line.discount
                    / 100
                )
            else:
                so_line.price_subtotal_before_discount = 0
