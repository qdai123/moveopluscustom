# -*- coding: utf-8 -*-
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

DISCOUNT_PERCENTAGE_DIVISOR = 100

MOVEOPLUS_TITLES = {
    "add_a_shipping_method": "Thêm phương thức giao hàng",
}

MOVEOPLUS_MESSAGES = {
    "discount_amount_apply_exceeded": "Tiền chiết khấu áp dụng không được lớn hơn số tiền chiết khấu tối đa.",
    "discount_amount_invalid": "Tiền chiết khấu áp dụng đang lớn hơn số tiền chiết khấu hiện có, vui lòng nhập lại!",
}


class MvWizardDeliveryCarrierAndDiscountPolicyApply(models.TransientModel):
    _name = "mv.wizard.discount"
    _description = _("Wizard: Delivery Carrier & Discount Policy Apply")

    def _get_default_weight_uom(self):
        return self.env[
            "product.template"
        ]._get_weight_uom_name_from_ir_config_parameter()

    set_to_zero = fields.Boolean(default=False)
    is_update = fields.Boolean(compute="_compute_sale_order_id")
    # === Sale Order Fields ===#
    sale_order_id = fields.Many2one("sale.order", required=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", related="sale_order_id.company_id")
    currency_id = fields.Many2one("res.currency", related="sale_order_id.currency_id")
    partner_id = fields.Many2one(
        "res.partner", related="sale_order_id.partner_id", required=True
    )
    # === Delivery Carrier Fields ===#
    delivery_set = fields.Boolean(compute="_compute_sale_order_id")
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
    discount_agency_set = fields.Boolean(compute="_compute_sale_order_id")
    discount_amount_invalid = fields.Boolean(readonly=True)
    discount_amount_invalid_message = fields.Text(readonly=True)
    discount_amount_apply = fields.Float()
    discount_amount_maximum = fields.Float(related="sale_order_id.bonus_max")
    discount_amount_remaining = fields.Float(compute="_compute_sale_order_id")
    discount_amount_applied = fields.Float(compute="_compute_sale_order_id")

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

    @api.onchange("set_to_zero")
    def _onchange_set_to_zero(self):
        if self.set_to_zero:
            self.discount_amount_apply = 0.0

    @api.onchange("discount_amount_invalid")
    def onchange_discount_amount_invalid_message(self):
        if self.discount_amount_invalid:
            self.discount_amount_invalid_message = MOVEOPLUS_MESSAGES[
                "discount_amount_invalid"
            ]

    @api.depends("partner_id", "sale_order_id", "sale_order_id.order_line")
    @api.depends_context("recompute_discount_agency")
    def _compute_sale_order_id(self):
        for wizard in self:
            order = wizard.sale_order_id
            partner = wizard.partner_id

            wizard.is_update = order.recompute_discount_agency
            wizard.delivery_set = self._has_delivery_line(order)
            wizard.discount_agency_set = self._has_discount_agency_lines(order)

            partner.action_update_discount_amount()
            if not self.env.context.get("recompute_discount_agency"):
                self._compute_discount_amounts(wizard, order, partner)
            else:
                wizard.discount_amount_remaining = order.bonus_remaining
                wizard.discount_amount_applied = order.bonus_order

    def _has_delivery_line(self, order):
        return any(line.is_delivery for line in order.order_line)

    def _has_discount_agency_lines(self, order):
        return order.order_line._filter_agency_lines(order)

    def _compute_discount_amounts(self, wizard, order, partner):
        partner_amount_remaining = partner.amount_currency
        wizard.discount_amount_remaining = max(partner_amount_remaining, 0.0)
        wizard.discount_amount_applied = (
            order.bonus_order
            if not wizard.discount_amount_invalid
            and partner_amount_remaining > order.bonus_order
            else 0.0
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

    @api.onchange("carrier_id", "total_weight")
    def _onchange_carrier_id(self):
        self.delivery_message = False
        if self.delivery_type in ("fixed", "base_on_rule"):
            vals = self._get_shipment_rate()
            if vals.get("error_message"):
                return {"error": vals["error_message"]}

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
            "default_code": "CKT",
            "type": "service",
            "invoice_policy": "order",
            "list_price": 0.0,
            "company_id": self.company_id.id,
            "taxes_id": None,
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

    def action_apply(self):
        wizard = self.with_company(self.company_id)
        order = wizard.sale_order_id

        if not wizard.delivery_set:
            order.set_delivery_line(wizard.carrier_id, wizard.delivery_price)
            order.write(
                {
                    "recompute_delivery_price": False,
                    "delivery_message": wizard.delivery_message,
                }
            )

        if not wizard.discount_agency_set:
            """Create SOline(s) discount according to wizard configuration"""
            order.compute_discount_for_partner(wizard.discount_amount_apply)

        # [>] Add Reward Line
        order.action_open_reward_wizard()

        # Create history line for discount
        if order.partner_id and order.partner_agency:
            selection_label = None
            if order.state == "draft":
                selection_label = "báo giá"
            elif order.state == "sent":
                selection_label = "báo giá đã gửi"
            is_waiting_approval = wizard.discount_amount_apply > 0
            self.env["mv.discount.partner.history"]._create_history_line(
                partner_id=order.partner_id.id,
                history_description=f"Đã áp dụng chiết khấu cho đơn {selection_label}, mã đơn là {order.name}. Đang chờ xác nhận.",
                sale_order_id=order.id,
                sale_order_state=order.get_selection_label(
                    order._name, "state", order.id
                )[1],
                sale_order_discount_money_apply=wizard.discount_amount_apply,
                total_money=wizard.discount_amount_apply,
                total_money_discount_display=(
                    "- {:,.2f}".format(wizard.discount_amount_apply)
                    if wizard.discount_amount_apply > 0
                    else "{:,.2f}".format(wizard.discount_amount_apply)
                ),
                is_waiting_approval=is_waiting_approval,
                is_positive_money=False,
                is_negative_money=False,
            )

        return True

    def action_update(self):
        wizard = self.with_company(self.company_id)
        order = wizard.sale_order_id

        if wizard.discount_agency_set:
            """Update SOline(s) discount according to wizard configuration"""

            order_line_agency = order.order_line.filtered(
                lambda line: line.product_id.default_code == "CKT"
                or line.is_discount_agency
            )
            total_order_discount_CKT = (
                (wizard.discount_amount_apply + wizard.discount_amount_applied)
                if wizard.discount_amount_remaining > 0
                else wizard.discount_amount_apply
            )
            total_price_after_update = (
                0 if wizard.set_to_zero else total_order_discount_CKT
            )
            if total_price_after_update != 0:
                order_line_agency.write({"price_unit": -total_price_after_update})
                order._compute_partner_bonus()
                order._compute_bonus_order_line()

        # [>] Add Reward Line
        order.action_open_reward_wizard()

        # [!] Should recompute discount agency
        order.should_recompute_discount_agency = False

        # [>] Create history line for discount
        if order.partner_id and order.partner_agency:
            selection_label = None
            if order.state == "draft":
                selection_label = "báo giá"
            elif order.state == "sent":
                selection_label = "báo giá đã gửi"
            is_waiting_approval = wizard.discount_amount_apply > 0
            self.env["mv.discount.partner.history"]._create_history_line(
                partner_id=order.partner_id.id,
                history_description=f"Đã cập nhật bổ sung chiết khấu cho đơn có {selection_label}, mã đơn là {order.name}. Đang chờ xác nhận.",
                sale_order_id=order.id,
                sale_order_state=order.get_selection_label(
                    order._name, "state", order.id
                )[1],
                sale_order_discount_money_apply=wizard.discount_amount_apply,
                total_money=wizard.discount_amount_apply,
                total_money_discount_display=(
                    "- {:,.2f}".format(wizard.discount_amount_apply)
                    if wizard.discount_amount_apply > 0
                    else "{:,.2f}".format(wizard.discount_amount_apply)
                ),
                is_waiting_approval=is_waiting_approval,
                is_positive_money=False,
                is_negative_money=False,
            )

        return True

    def action_apply_and_confirm(self):
        self.action_update()
        self.sale_order_id.write({"should_recompute_discount_agency": False})
        return self.sale_order_id.with_context(apply_confirm=True).action_confirm()
