# -*- coding: utf-8 -*-
import logging

from markupsafe import Markup
from odoo.addons.mv_sale.models.sale_order import GROUP_SALES_MANAGER

from odoo import api, fields, models
from odoo.tools.sql import column_exists, create_column

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    is_promotion = fields.Boolean(related='product_id.is_promotion', store=True)

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

    code_product = fields.Char("Product Code")
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
        "Agency Discount Product",
        compute="_is_discount_agency",
        store=True,
        compute_sudo=True,
    )
    recompute_discount_agency = fields.Boolean(default=False)

    # === Permission/Flags Fields ===#
    is_sales_manager = fields.Boolean(compute="_compute_permissions")

    @api.depends("order_id")
    @api.depends_context("uid")
    def _compute_permissions(self):
        for sol in self:
            sol.is_sales_manager = self.env.user.has_group(GROUP_SALES_MANAGER)

    # /// ORM Methods

    @api.depends("product_id", "product_id.default_code")
    def _is_discount_agency(self):
        for sol in self:
            sol.is_discount_agency = sol._filter_discount_agency_lines(sol.order_id)

    @api.depends("qty_delivered", "price_unit", "discount")
    def _compute_price_subtotal_before_discount(self):
        for sol in self:
            try:
                if sol.price_unit and sol.qty_delivered and sol.discount:
                    sol.price_subtotal_before_discount = (
                        sol.price_unit * sol.qty_delivered
                    ) - ((sol.price_unit * sol.qty_delivered) * sol.discount / 100)
                else:
                    sol.price_subtotal_before_discount = 0
            except Exception as e:
                _logger.error(
                    f"Error computing subtotal before discount for line {sol.id}: {e}"
                )
                sol.price_subtotal_before_discount = 0

    def _compute_product_updatable(self):
        service_lines = self.filtered(
            lambda line: line.product_template_id.detailed_type == "service"
            and line.state not in ["cancel", "sale"]
            and not line.is_sales_manager
        )
        super(SaleOrderLine, self - service_lines)._compute_product_updatable()
        service_lines.product_updatable = True

    def _compute_product_uom_readonly(self):
        service_lines = self.filtered(
            lambda line: line.ids
            and line.product_template_id.detailed_type == "service"
            and line.state not in ["cancel", "sale"]
            and not line.is_sales_manager
        )
        super(SaleOrderLine, self - service_lines)._compute_product_uom_readonly()
        service_lines.product_uom_readonly = True

    # /// CRUD Methods

    @api.model
    def create(self, vals):
        if "product_id" in vals and not vals.get("code_product"):
            product = self.env["product.product"].browse(vals["product_id"])
            vals["code_product"] = product.default_code
        return super(SaleOrderLine, self).create(vals)

    def write(self, vals):
        if "product_id" in vals and not vals.get("code_product"):
            product = self.env["product.product"].browse(vals["product_id"])
            vals["code_product"] = product.default_code

        res = super(SaleOrderLine, self).write(vals)

        if any(sol.hidden_show_qty or sol.reward_id for sol in self):
            return res
        else:
            if "product_uom_qty" in vals and vals["product_uom_qty"]:
                for sol in self:
                    sol._set_recompute_discount_agency()
                    sol.order_id._reset_discount_agency(sol.order_id.state)

            return res

    def _set_recompute_discount_agency(self):
        """
        Set the recompute_discount_agency flag to True for lines that need it.
        """
        lines_to_update = self._get_discount_agency_line()
        lines_to_update.write({"recompute_discount_agency": True})

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

    # MOVEO+ OVERRIDE: Force to delete the record if it's not confirmed by Sales Manager
    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        if not self.env.user.has_group(GROUP_SALES_MANAGER):
            return super(SaleOrderLine, self)._unlink_except_confirmed()

    # /// HOOKS Methods

    def _is_not_sellable_line(self):
        return (
            self.hidden_show_qty
            or self.is_discount_agency
            or super()._is_not_sellable_line()
        )

    # /// HELPERS Methods

    def _get_discount_agency_line(self):
        return self._filter_discount_agency_lines(self.order_id)

    def _filter_discount_agency_lines(self, order=False):
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
