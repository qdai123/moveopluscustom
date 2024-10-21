# -*- coding: utf-8 -*-
import logging
from datetime import date, timedelta

from odoo import api, fields, models
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


class MvDiscountProductWarrantyPolicy(models.Model):
    _name = "mv.discount.product.warranty.policy"
    _description = "Chính sách chiết khấu kích hoạt bảo hành theo sản phẩm"
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
        "res_company_mv_discount_product_warranty_policy_rel",
        "company_id",
        "policy_id",
        "Companies",
        default=lambda self: self.env.company,
    )
    mv_partner_ids = fields.Many2many(
        "mv.discount.partner",
        "mv_partner_discount_product_warranty_policy_rel",
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
    product_apply_reward_ids = fields.One2many(
        "mv.product.reward.apply.line",
        "policy_id",
        "Product Apply Reward",
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
            self.env["mv.discount.product.warranty.policy"].search_count(
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


class MvProductRewardApplyLine(models.Model):
    _name = _description = "mv.product.reward.apply.line"
    _rec_name = "product_id"

    PRODUCT_FOR_SALE_DOMAIN = [
        ("product_tmpl_id.sale_ok", "=", True),
        ("product_tmpl_id.detailed_type", "=", "product"),
    ]

    policy_id = fields.Many2one(
        "mv.discount.product.warranty.policy",
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
        "product.template",
        "Product Template",
        compute="_compute_product_template_id",
        readonly=False,
        search="_search_product_template_id",
        domain=PRODUCT_FOR_SALE_DOMAIN,
    )
    reward_amount = fields.Monetary("Reward", currency_field="company_currency_id")

    @api.constrains("product_id")
    def _check_duplicate_policy_line(self):
        for line in self:
            if self._does_record_exist(line):
                raise ValidationError(
                    "Sản phẩm này đã được áp dụng trong chính sách khác, vui lòng kiểm tra lại!"
                )

    def _does_record_exist(self, policy):
        return (
            self.env["mv.product.reward.apply.line"].search_count(
                [("id", "!=", policy.id), ("product_id", "=", policy.product_id.id)]
            )
            > 0
        )

    @api.depends("product_id")
    def _compute_product_template_id(self):
        for line in self:
            line.product_template_id = line.product_id.product_tmpl_id

    def _search_product_template_id(self, operator, value):
        return [("product_id.product_tmpl_id", operator, value)]

    @api.autovacuum
    def _gc_policy_product_reward_apply(self):
        """Delete all policy lines that are not linked to the parent policy."""
        lines_to_del = self.env["mv.product.reward.apply.line"].search(
            [("policy_id", "=", False)]
        )
        if lines_to_del:
            lines_to_del.unlink()
            _logger.info("Successfully deleted unlinked policy lines.")
        else:
            _logger.info("No unlinked policy lines found.")
