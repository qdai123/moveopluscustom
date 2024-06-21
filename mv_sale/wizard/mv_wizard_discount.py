# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

MOVEOPLUS_TITLES = {
    "add_a_shipping_method": "Thêm phương thức giao hàng",
}

MOVEOPLUS_MESSAGES = {
    "discount_amount_apply_exceeded": "Tổng tiền chiết khấu không được lớn hơn Số tiền chiết khấu tối đa.",
}


class MvWizardDeliveryCarrierAndDiscountPolicyApply(models.TransientModel):
    _name = "mv.wizard.discount"
    _description = _("Wizard: Delivery Carrier & Discount Policy Apply")

    def _get_default_weight_uom(self):
        return self.env[
            "product.template"
        ]._get_weight_uom_name_from_ir_config_parameter()

    sale_order_id = fields.Many2one("sale.order", required=True)
    company_id = fields.Many2one("res.company", related="sale_order_id.company_id")
    currency_id = fields.Many2one("res.currency", related="sale_order_id.currency_id")
    partner_id = fields.Many2one(
        "res.partner", related="sale_order_id.partner_id", required=True
    )

    # === Delivery Carrier Fields ===#
    delivery_set = fields.Boolean(compute="_compute_invisible")
    carrier_id = fields.Many2one("delivery.carrier", required=True)
    delivery_type = fields.Selection(related="carrier_id.delivery_type")
    delivery_price = fields.Float()
    display_price = fields.Float(string="Cost", readonly=True)
    available_carrier_ids = fields.Many2many(
        "delivery.carrier",
        compute="_compute_available_carrier",
        string="Available Carriers",
    )
    invoicing_message = fields.Text(compute="_compute_invoicing_message")
    delivery_message = fields.Text(readonly=True)
    total_weight = fields.Float(
        string="Total Order Weight",
        related="sale_order_id.shipping_weight",
        readonly=False,
    )
    weight_uom_name = fields.Char(readonly=True, default=_get_default_weight_uom)

    # === Discount Policy Fields ===#
    discount_product_ckt_set = fields.Boolean(compute="_compute_invisible")
    discount_amount_apply = fields.Float()
    discount_amount_remaining = fields.Float(related="sale_order_id.bonus_remaining")
    discount_amount_maximum = fields.Float(related="sale_order_id.bonus_max")
    discount_amount_applied = fields.Float(related="sale_order_id.bonus_order")

    # ==================================
    # CONSTRAINS / VALIDATION Methods
    # ==================================

    @api.constrains(
        "discount_amount_apply", "discount_amount_applied", "discount_amount_maximum"
    )
    def _check_discount_amount_apply_exceeded(self):
        for wizard in self:
            total_applied = (
                wizard.discount_amount_applied + wizard.discount_amount_apply
            )
            if (
                wizard.discount_amount_applied == 0
                and wizard.discount_amount_apply > wizard.discount_amount_maximum
            ) or (
                wizard.discount_amount_applied != 0
                and total_applied > wizard.discount_amount_maximum
            ):
                raise ValidationError(
                    MOVEOPLUS_MESSAGES["discount_amount_apply_exceeded"]
                )

    # ==================================
    # COMPUTE / ONCHANGE Methods
    # ==================================

    @api.depends("sale_order_id", "sale_order_id.order_line")
    def _compute_invisible(self):
        for wizard in self:
            wizard.delivery_set = any(
                line.is_delivery for line in wizard.sale_order_id.order_line
            )
            wizard.discount_product_ckt_set = any(
                line.product_id.default_code == "CKT"
                for line in wizard.sale_order_id.order_line
            )

    @api.depends("carrier_id")
    def _compute_invoicing_message(self):
        self.ensure_one()
        self.invoicing_message = ""

    @api.depends("partner_id")
    def _compute_available_carrier(self):
        for rec in self:
            carriers = self.env["delivery.carrier"].search(
                self.env["delivery.carrier"]._check_company_domain(
                    rec.sale_order_id.company_id
                )
            )
            rec.available_carrier_ids = (
                carriers.available_carriers(rec.sale_order_id.partner_shipping_id)
                if rec.partner_id
                else carriers
            )

    @api.onchange("carrier_id", "total_weight")
    def _onchange_carrier_id(self):
        self.delivery_message = False
        if self.delivery_type in ("fixed", "base_on_rule"):
            vals = self._get_shipment_rate()
            if vals.get("error_message"):
                return {"error": vals["error_message"]}
        else:
            self.display_price = 0
            self.delivery_price = 0

    @api.onchange("sale_order_id")
    def _onchange_order_id(self):
        # fixed and base_on_rule delivery price will compute on each carrier change so no need to recompute here
        if (
            self.carrier_id
            and self.sale_order_id.delivery_set
            and self.delivery_type not in ("fixed", "base_on_rule")
        ):
            vals = self._get_shipment_rate()
            if vals.get("error_message"):
                warning = {
                    "title": _("%(carrier)s Error", carrier=self.carrier_id.name),
                    "message": vals["error_message"],
                    "type": "notification",
                }
                return {"warning": warning}

    # ==================================
    # BUSINESS Methods
    # ==================================

    def _get_shipment_rate(self):
        vals = self.carrier_id.with_context(
            order_weight=self.total_weight
        ).rate_shipment(self.sale_order_id)
        if vals.get("success"):
            self.delivery_message = vals.get("warning_message", False)
            self.delivery_price = vals["price"]
            self.display_price = vals["carrier_price"]
            return {}
        return {"error_message": vals["error_message"]}

    def update_price(self):
        vals = self._get_shipment_rate()
        if vals.get("error_message"):
            raise UserError(vals.get("error_message"))
        return {
            "name": MOVEOPLUS_TITLES["add_a_shipping_method"],
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "choose.delivery.carrier",
            "res_id": self.id,
            "target": "new",
        }

    def _prepare_mv_discount_product_ckt_values(self):
        self.ensure_one()
        return {
            "name": "Chiết khấu sản lượng (Tháng, Quý, Năm)",
            "type": "service",
            "invoice_policy": "order",
            "list_price": 0.0,
            "company_id": self.company_id.id,
            "taxes_id": None,
            "default_code": "CKT",
        }

    def _prepare_mv_discount_line_values(self, product, amount, description=None):
        self.ensure_one()

        vals = {
            "order_id": self.sale_order_id.id,
            "product_id": product.id,
            "product_uom_qty": 1,
            "code_product": "CKT",
            "price_unit": -amount,
            "hidden_show_qty": True,
            "sequence": 999,
        }
        if description:
            # If not given, name will fall back on the standard SOL logic (cf. _compute_name)
            vals["name"] = description

        return vals

    def _get_mv_discount_product(self):
        """Return product.product used for moveoplus discount line"""
        self.ensure_one()
        discount_product = self.env["product.product"].search(
            [("default_code", "=", "CKT")], limit=1
        )
        if not discount_product:
            self.company_id.sale_discount_product_id = self.env[
                "product.product"
            ].create(self._prepare_mv_discount_product_ckt_values())
            discount_product = self.company_id.sale_discount_product_id
        return discount_product

    def _create_mv_discount_lines(self):
        """Create SOline(s) according to wizard configuration"""
        self.ensure_one()

        discount_product = self._get_mv_discount_product()

        vals_list = [
            {
                **self._prepare_mv_discount_line_values(
                    product=discount_product, amount=self.discount_amount_apply
                ),
            }
        ]

        return self.env["sale.order.line"].create(vals_list)

    def action_apply_discount(self):
        self.ensure_one()
        self = self.with_company(self.company_id)
        try:
            order = self.sale_order_id
            order.set_delivery_line(self.carrier_id, self.delivery_price)
            order.write(
                {
                    "recompute_delivery_price": False,
                    "delivery_message": self.delivery_message,
                }
            )
            if not self.discount_product_ckt_set:
                self._create_mv_discount_lines()
        except Exception as e:
            _logger.error("Unexpected error: %s", e)
            raise UserError(_("An unexpected error occurred. Please try again."))

    # ==================================
    # TOOLING
    # ==================================

    def _format_currency_amount(self, currency, amount):
        pre = post = ""
        if currency.position == "before":
            pre = "{symbol}\N{NO-BREAK SPACE}".format(symbol=currency.symbol or "")
        else:
            post = "\N{NO-BREAK SPACE}{symbol}".format(symbol=currency.symbol or "")
        return " {pre}{0}{post}".format(amount, pre=pre, post=post)
