# -*- coding: utf-8 -*-
import logging
from datetime import date, datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

_logger = logging.getLogger(__name__)

DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT,
)

POLICY_APPROVER = "mv_sale.group_mv_compute_discount_approver"
POLICY_STATUS = [
    ("open", "Sẵn sàng"),
    ("applying", "Đang Áp Dụng"),
    ("close", "Đã kết thúc"),
]
POLICY_TYPE = [("disc_product", "Product Disc.%")]


def get_years():
    return [(str(i), str(i)) for i in range(2000, datetime.now().year + 1)]


def get_months():
    return [(str(i), str(i)) for i in range(1, 13)]


class MvDiscountPolicy(models.Model):
    _name = "mv.discount.policy"
    _inherit = ["mail.thread"]
    _description = "Chính sách chiết khấu giảm giá"
    _rec_name = "policy_name"

    def _default_can_access(self):
        user = self.env.user
        return user.has_group(POLICY_APPROVER) or user._is_admin() or user._is_system()

    @api.depends_context("uid")
    def _can_access(self):
        for policy in self:
            policy.can_access = self._fully_access()

    can_access = fields.Boolean(
        compute="_can_access",
        default=lambda self: self._default_can_access(),
    )
    active = fields.Boolean(default=True)
    company_ids = fields.Many2many(
        "res.company",
        "res_company_mv_discount_policy_rel",
        "company_id",
        "policy_id",
        "Companies",
        default=lambda self: self.env.company,
    )
    mv_partner_ids = fields.Many2many(
        "mv.discount.partner",
        "mv_partner_discount_policy_rel",
        "mv_partner_discount_id",
        "policy_id",
        "Partners",
        domain=[("partner_id.is_agency", "=", True)],
    )
    date_from = fields.Date(default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(
        default=lambda self: (date.today().replace(day=1) + timedelta(days=32)).replace(
            day=1
        )
        - timedelta(days=1)
    )
    policy_name = fields.Char("Policy", required=True)
    policy_status = fields.Selection(POLICY_STATUS, "Status", default="open")
    policy_description = fields.Html("Description")
    policy_type = fields.Selection(
        POLICY_TYPE,
        "Policy Type",
        default="disc_product",
    )
    # ---- Products Disc.% Fields ---- #
    policy_level_quantity_ids = fields.One2many(
        "mv.discount.policy.level.quantity.line",
        "policy_id",
        "Level Quantity",
    )
    policy_product_level_ids = fields.One2many(
        "mv.discount.policy.product.level.line",
        "policy_id",
        "Product Level",
    )

    # =================================
    # CONSTRAINS Methods
    # =================================

    @api.constrains("company_ids", "date_from", "date_to")
    def _validate_already_exist_policy(self):
        for policy in self:
            if self._is_policy_date_range_valid(policy):
                if self._does_policy_exist(policy):
                    raise ValidationError(
                        "Chính sách này đã bị trùng, vui lòng kiểm tra lại!"
                    )

    def _is_policy_date_range_valid(self, policy):
        return policy.date_from and policy.date_to

    def _does_policy_exist(self, policy):
        return (
            self.env["mv.discount.policy"].search_count(
                [
                    ("id", "!=", policy.id),
                    ("company_ids", "in", policy.company_ids.ids),
                    ("date_from", ">=", policy.date_from),
                    ("date_to", "<=", policy.date_to),
                    ("active", "=", True),
                ]
            )
            > 0
        )

    # =================================
    # ORM/CRUD Methods
    # =================================

    @api.onchange("date_from")
    def _onchange_date_from(self):
        if self.date_from:
            self.date_to = (self.date_from + timedelta(days=32)).replace(
                day=1
            ) - timedelta(days=1)

    # =================================
    # ACTION Methods
    # =================================

    def load_partners(self):
        """
        Load all partners that are agencies and not in the current policy.
        :return: list of partners has been added to the policy.
        """
        self.ensure_one()
        existing_partner_ids = self.mv_partner_ids.ids

        def _get_new_partners(existing_partner_ids):
            return self.env["mv.discount.partner"].search(
                [
                    ("partner_id.is_agency", "=", True),
                    ("id", "not in", existing_partner_ids),
                ]
            )

        def _update_existing_agency_partners(agency_partners):
            for partner in self.env["res.partner"].browse(agency_partners):
                if (
                    partner.is_agency
                    and partner.use_for_report
                    and not partner.discount_policy_ids
                ):
                    partner.discount_policy_ids = [(6, 0, self.ids)]

        new_partners = _get_new_partners(existing_partner_ids)
        self.mv_partner_ids = [(4, partner.id) for partner in new_partners]

        if existing_partner_ids:
            # _update_existing_agency_partners(existing_partner_ids)
            _logger.debug("Updated existing partners.")

    def _check_access(self):
        self.ensure_one()

        if not self._fully_access():
            raise AccessError(
                "Bạn không có quyền thao tác, vui lòng liên hệ người có thẩm quyền!"
            )

    def action_reset_to_open(self):
        self._check_access()
        self.write({"policy_status": "open"})

    def action_apply(self):
        self._check_access()
        if self.policy_status == "open":
            self.write({"policy_status": "applying"})
        return True

    def action_close(self):
        self._check_access()
        if self.policy_status == "applying":
            self.write({"policy_status": "close"})
        return True

    # =================================
    # HELPER / PRIVATE Methods
    # =================================

    def _fully_access(self):
        return (
            self.env.user.has_group(POLICY_APPROVER)
            or self.env.user._is_admin()
            or self.env.user._is_system()
        )


class MvDiscountPolicyLevelQuantityLine(models.Model):
    _name = _description = "mv.discount.policy.level.quantity.line"

    policy_id = fields.Many2one(
        "mv.discount.policy",
        "Policy",
        ondelete="cascade",
        readonly=True,
    )
    name = fields.Char("Name", compute="_compute_name", store=True)
    level = fields.Integer("Level", required=True)
    quantity_min = fields.Integer("Min Qty", default=1, required=True)
    quantity_max = fields.Integer("Max Qty", default=1, required=True)

    _sql_constraints = [
        (
            "policy_level_uniq",
            "unique(policy_id, level)",
            "The level of the policy must be unique!",
        )
    ]

    @api.constrains("level")
    def _check_level_limited(self):
        for record in self:
            if record.level < 0 or record.level > 4:
                raise ValidationError("Level must be in range 0-4!")

    @api.constrains("quantity_min", "quantity_max")
    def _check_quantity_range(self):
        for record in self:
            if record.quantity_min > record.quantity_max:
                raise ValidationError("Min quantity must be less than Max quantity!")

    @api.depends("policy_id", "level", "quantity_min", "quantity_max")
    def _compute_name(self):
        for record in self:
            policy_name = record.policy_id.policy_name
            level = record.level
            quantity_min = record.quantity_min
            quantity_max = record.quantity_max
            record.name = f"{policy_name} - Level {level} (Min: {quantity_min} - Max: {quantity_max})"

    @api.autovacuum
    def _gc_policy_level_quantity(self):
        """Delete all policy lines that are not linked to the parent policy."""
        lines_to_del = self.env["mv.discount.policy.level.quantity.line"].search(
            [("policy_id", "=", False)]
        )
        if lines_to_del:
            lines_to_del.unlink()
            _logger.info("Successfully deleted unlinked policy lines.")
        else:
            _logger.info("No unlinked policy lines found.")


class MvDiscountPolicyProductLevelLine(models.Model):
    _name = _description = "mv.discount.policy.product.level.line"
    _rec_name = "product_id"

    PRODUCT_FOR_SALE_DOMAIN = [
        ("sale_ok", "=", True),
        ("detailed_type", "=", "product"),
    ]

    policy_id = fields.Many2one(
        "mv.discount.policy",
        "Policy",
        ondelete="cascade",
        readonly=True,
    )
    company_currency_id = fields.Many2one(
        "res.currency",
        "Company Currency",
        readonly=True,
        default=lambda self: self.env.company.currency_id,
    )
    product_id = fields.Many2one(
        "product.product",
        "Product",
        change_default=True,
        ondelete="restrict",
        index="btree_not_null",
        required=True,
        domain=[
            ("product_tmpl_id.sale_ok", "=", True),
            ("product_tmpl_id.detailed_type", "=", "product"),
        ],
    )
    product_template_id = fields.Many2one(
        comodel_name="product.template",
        string="Product Template",
        compute="_compute_product_template_id",
        readonly=False,
        search="_search_product_template_id",
        domain=PRODUCT_FOR_SALE_DOMAIN,
    )
    product_custom_attribute_value_ids = fields.One2many(
        comodel_name="product.attribute.custom.value",
        inverse_name="mv_discount_policy_product_level_id",
        string="Custom Values",
        compute="_compute_custom_attribute_values",
        store=True,
        readonly=False,
        precompute=True,
        copy=True,
    )
    product_no_variant_attribute_value_ids = fields.Many2many(
        comodel_name="product.template.attribute.value",
        relation="mv_discount_policy_product_level_line_extra_value_rel",
        column1="policy_product_level_id",
        column2="product_template_attribute_value_id",
        string="Extra Values",
        compute="_compute_no_variant_attribute_values",
        store=True,
        readonly=False,
        precompute=True,
        ondelete="restrict",
    )
    price_level_0 = fields.Monetary("Level 0", currency_field="company_currency_id")
    price_level_1 = fields.Monetary("Level 1", currency_field="company_currency_id")
    price_level_2 = fields.Monetary("Level 2", currency_field="company_currency_id")
    price_level_3 = fields.Monetary("Level 3", currency_field="company_currency_id")
    price_level_4 = fields.Monetary("Level 4", currency_field="company_currency_id")

    @api.depends("product_id")
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [("product_id.product_tmpl_id", operator, value)]

    @api.depends("product_id")
    def _compute_custom_attribute_values(self):
        for line in self:
            if not line.product_id:
                line.product_custom_attribute_value_ids = False
            else:
                self._remove_invalid_custom_attribute_values(line)

    @api.depends("product_id")
    def _compute_no_variant_attribute_values(self):
        for line in self:
            if not line.product_id:
                line.product_no_variant_attribute_value_ids = False
            else:
                self._remove_invalid_no_variant_attribute_values(line)

    def _remove_invalid_custom_attribute_values(self, line):
        valid_values = (
            line.product_id.product_tmpl_id.valid_product_template_attribute_line_ids.product_template_value_ids
        )
        for custom_value in line.product_custom_attribute_value_ids:
            if (
                custom_value.custom_product_template_attribute_value_id
                not in valid_values
            ):
                line.product_custom_attribute_value_ids -= custom_value

    def _remove_invalid_no_variant_attribute_values(self, line):
        valid_values = (
            line.product_id.product_tmpl_id.valid_product_template_attribute_line_ids.product_template_value_ids
        )
        for extra_value in line.product_no_variant_attribute_value_ids:
            if extra_value._origin not in valid_values:
                line.product_no_variant_attribute_value_ids -= extra_value

    @api.autovacuum
    def _gc_policy_product_by_level(self):
        """Delete all policy lines that are not linked to the parent policy."""
        lines_to_del = self.env["mv.discount.policy.product.level.line"].search(
            [("policy_id", "=", False)]
        )
        if lines_to_del:
            lines_to_del.unlink()
            _logger.info("Successfully deleted unlinked policy lines.")
        else:
            _logger.info("No unlinked policy lines found.")
