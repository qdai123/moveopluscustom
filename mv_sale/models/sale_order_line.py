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

    code_product = fields.Char()
    price_subtotal_before_discount = fields.Monetary(
        "Subtotal before Discount",
        compute="_compute_price_subtotal_before_discount",
        store=True,
        currency_field="currency_id",
    )
    hidden_show_qty = fields.Boolean(help="Don't show change Quantity on Website")
    discount_line_id = fields.Many2one("mv.compute.discount.line")
    is_discount_agency = fields.Boolean(
        "Agency Discount Product",
        compute="_is_discount_agency",
        store=True,
        compute_sudo=True,
    )
    recompute_discount_agency = fields.Boolean(
        related="order_id.recompute_discount_agency"
    )

    # /// ORM Methods (OVERRIDE)

    def _compute_product_updatable(self):
        super()._compute_product_updatable()

        for sol in self:
            sol.product_updatable = (
                not sol.is_sales_manager
                and sol.state not in ["cancel", "sale"]
                and sol.product_template_id.detailed_type == "service"
            )

    def _compute_product_uom_readonly(self):
        super()._compute_product_uom_readonly()

        for sol in self:
            sol.product_uom_readonly = (
                sol.ids
                and sol.state in ["sale", "cancel"]
                or (
                    not sol.is_sales_manager
                    and sol.product_template_id.detailed_type == "service"
                )
            )

    # /// CRUD Methods

    def write(self, vals):
        if any(sol.hidden_show_qty or sol.reward_id for sol in self):
            return super().write(vals)

        result = super().write(vals)

        if "product_uom_qty" in vals and vals.get("product_uom_qty"):
            unique_orders = set(sol.order_id for sol in self)
            for order in unique_orders:
                order.action_clear_discount_lines()

        return result

    def unlink(self):
        orders_to_update = self.filtered(
            lambda sol: sol.product_id
            and sol.product_id.default_code
            and "Delivery_" not in sol.product_id.default_code
        ).mapped("order_id")

        unique_orders = set(orders_to_update)
        for order in unique_orders:
            order._compute_partner_bonus()
            order._compute_bonus_order_line()

        return super().unlink()

    # MOVEO+ OVERRIDE: Force to delete the record if it's not confirmed by Sales Manager
    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        if not self.env.user.has_group(GROUP_SALES_MANAGER):
            return super(SaleOrderLine, self)._unlink_except_confirmed()

    # /// HOOKS Methods

    def _is_not_sellable_line(self):
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

    @api.depends("product_id", "product_id.default_code")
    def _is_discount_agency(self):
        for sol in self:
            sol.is_discount_agency = sol._filter_discount_agency_lines(sol.order_id)

    @api.depends("price_unit", "qty_delivered", "discount")
    def _compute_price_subtotal_before_discount(self):
        for sol in self:
            if sol.price_unit and sol.qty_delivered and sol.discount:
                sol.price_subtotal_before_discount = (
                    sol.price_unit * sol.qty_delivered
                ) - ((sol.price_unit * sol.qty_delivered) * sol.discount / 100)
            else:
                sol.price_subtotal_before_discount = 0

    # /// CONSTRAINTS Methods

    @api.constrains("order_id", "order_id.sate")
    def _check_product_qty(self):
        for sol in self:
            if sol.product_id and sol.product_id.default_code:
                if sol.product_id.default_code == "CKT" and sol.product_uom_qty < 0:
                    raise ValidationError(
                        _("The quantity of the product must be greater than 0.")
                    )
