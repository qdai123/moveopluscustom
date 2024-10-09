# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup
from odoo.addons.mv_sale.models.sale_order import GROUP_SALES_MANAGER

from odoo import api, fields, models
from odoo.tools.sql import column_exists, create_column

_logger = logging.getLogger(__name__)

SERVICE_TYPE = "service"
AGENCY_CODE = "CKT"


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    is_promotion = fields.Boolean(related='product_id.is_promotion', store=True)

    code_product = fields.Char("Product Code")
    price_discount_inv = fields.Monetary(
        "Price Disc.%",
        compute="_compute_price_total_before_discount",
        store=True,
        currency_field="currency_id",
    )
    price_total_before_discount = fields.Monetary(
        "Price Before Disc.%",
        compute="_compute_price_total_before_discount",
        store=True,
        currency_field="currency_id",
    )
    price_subtotal_before_discount = fields.Monetary(
        "Subtotal before Discount",
        compute="_compute_price_subtotal_before_discount",
        store=True,
        currency_field="currency_id",
    )
    hidden_show_qty = fields.Boolean(help="Don't show change Quantity on Website")
    discount_line_id = fields.Many2one(
        "mv.compute.discount.line",
        "Discount Line by Policy",
        readonly=True,
    )
    is_discount_agency = fields.Boolean(
        "Product Agency (Disc.%)",
        compute="_is_discount_agency",
        store=True,
        compute_sudo=True,
    )
    recompute_discount_agency = fields.Boolean(default=False)

    # === Permission/Flags Fields ===#
    is_sales_manager = fields.Boolean(compute="_compute_permissions")

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

    @api.depends("order_id")
    @api.depends_context("uid")
    def _compute_permissions(self):
        """Computes whether the user has manager permissions"""
        for sol in self:
            sol.is_sales_manager = self.env.user.has_group(GROUP_SALES_MANAGER)

    @api.depends("product_id", "product_id.default_code")
    def _is_discount_agency(self):
        """Determines if the line is a discount agency"""
        for sol in self:
            sol.is_discount_agency = sol._filter_agency_lines(sol.order_id)

    @api.depends("product_uom_qty", "price_unit", "price_subtotal", "product_id")
    def _compute_price_total_before_discount(self):
        for sol in self:
            # Continue only if the product is not a reward and is not service
            if sol.product_id and not sol.reward_id and not sol.is_service:
                sol.price_total_before_discount = sol.price_unit * sol.product_uom_qty
                sol.price_discount_inv = (
                    sol.price_total_before_discount - sol.price_subtotal
                )
            else:
                sol.price_total_before_discount = 0.0
                sol.price_discount_inv = 0.0

    @api.depends("price_unit", "qty_delivered", "discount")
    def _compute_price_subtotal_before_discount(self):
        """Computes the price subtotal before applying discounts"""
        for sol in self:
            sol.price_subtotal_before_discount = (
                self._calculate_subtotal_before_discount(
                    sol.price_unit, sol.qty_delivered, sol.discount
                )
            )
            self._log_price_subtotal(sol.id, sol.price_subtotal_before_discount)

    def _calculate_subtotal_before_discount(self, price_unit, qty_delivered, discount):
        if price_unit and qty_delivered:
            subtotal = price_unit * qty_delivered
            discount_amount = subtotal * discount / 100
            return subtotal - discount_amount
        return 0

    def _log_price_subtotal(self, sol_id, price_subtotal_before_discount):
        _logger.info(
            f"Computed subtotal before discount for line {sol_id}: {price_subtotal_before_discount}"
        )

    def _compute_product_updatable(self):
        service_lines = self._filter_service_lines_excluding_states(["cancel", "sale"])
        super(SaleOrderLine, self - service_lines)._compute_product_updatable()
        service_lines.product_updatable = True

    def _compute_product_uom_readonly(self):
        service_lines = self._filter_service_lines_excluding_states(["cancel", "sale"])
        super(SaleOrderLine, self - service_lines)._compute_product_uom_readonly()
        service_lines.product_uom_readonly = True

    def _set_product_code(self, vals):
        """Helper method to set product code from the product."""
        if "product_id" in vals and not vals.get("code_product"):
            product = self.env["product.product"].browse(vals["product_id"])
            vals["code_product"] = product.default_code

    def _set_recompute_discount_agency(self):
        """Set the recompute_discount_agency flag to True for lines that need it"""
        lines_to_update = self._filter_agency_lines(self.order_id)
        lines_to_update.write({"recompute_discount_agency": True})

    @api.model
    def create(self, vals):
        self._set_product_code(vals)
        return super(SaleOrderLine, self).create(vals)

    def write(self, vals):
        self._set_product_code(vals)
        res = super(SaleOrderLine, self).write(vals)
        if any(sol.hidden_show_qty or sol.reward_id for sol in self):
            return res
        if "product_uom_qty" in vals and vals["product_uom_qty"]:
            for sol in self:
                sol._set_recompute_discount_agency()
                sol.order_id._reset_discount_agency(sol.order_id.state)
        return res

    def unlink(self):
        for sol in self:
            if sol.is_service and sol.is_discount_agency:
                sol.order_id.message_notify(
                    body=Markup(
                        "Line %s has been deleted, amount: %s"
                        % (sol.product_id.name, sol.price_unit)
                    )
                )
        return super(SaleOrderLine, self).unlink()

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        """Override unlink method to prevent deletion unless confirmed by Sales Manager"""
        if not self.env.user.has_group(GROUP_SALES_MANAGER):
            return super(SaleOrderLine, self)._unlink_except_confirmed()

    def _filter_agency_lines(self, order=False):
        """Filters the discount agency lines for the given order"""
        try:
            if not order:
                return self.browse()
            return order.order_line.filtered(
                lambda sol: sol.product_id.product_tmpl_id.detailed_type == SERVICE_TYPE
                and sol.product_id.default_code == AGENCY_CODE
            )
        except Exception as e:
            _logger.error(f"Failed to filter agency order lines: {e}")
            return self.env["sale.order.line"]

    def _filter_service_lines_excluding_states(self, excluded_states):
        """Filters the service lines excluding the provided states"""
        return self.filtered(
            lambda line: line.product_template_id.detailed_type == SERVICE_TYPE
            and line.state not in excluded_states
            and not line.is_sales_manager
        )

    def _is_not_sellable_line(self):
        return (
            self.hidden_show_qty
            or self.is_discount_agency
            or super()._is_not_sellable_line()
        )
