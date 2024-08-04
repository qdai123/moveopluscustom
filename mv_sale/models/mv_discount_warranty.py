# -*- coding: utf-8 -*-
import base64
import io
import logging
import re
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError, MissingError
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)

DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT,
)

DISCOUNT_APPROVER = "mv_sale.group_mv_compute_discount_approver"

# Ticket Type Codes for Warranty Activation:
SUB_DEALER_CODE = "kich_hoat_bao_hanh_dai_ly"
END_USER_CODE = "kich_hoat_bao_hanh_nguoi_dung_cuoi"


def get_years():
    return [(str(i), str(i)) for i in range(2000, datetime.now().year + 1)]


def get_months():
    return [(str(i), str(i)) for i in range(1, 13)]


def convert_to_code(text):
    # Convert to lowercase
    text = text.lower()

    # Replace relational operators
    replacements = {
        "<=": "lower_and_equal",
        ">=": "greater_and_equal",
        "<": "lower_than",
        ">": "greater_than",
        "=": "equal",
    }

    for key, value in replacements.items():
        text = text.replace(key, value)

    # Replace spaces and other non-alphanumeric characters with underscores
    text = re.sub(r"\s+|[^a-zA-Z0-9]", "_", text)

    # Remove leading or trailing underscores
    text = text.strip("_")

    return text


class MvWarrantyDiscountPolicy(models.Model):
    _name = "mv.warranty.discount.policy"
    _description = _("Warranty Discount Policy")
    _order = "date_from desc, date_to desc"

    # ACCESS/RULE Fields:
    can_access = fields.Boolean(
        compute="_compute_can_access",
        default=lambda self: self.env.user.has_group(DISCOUNT_APPROVER)
        or self.env.user._is_admin()
        or self.env.user._is_system(),
    )

    @api.depends_context("uid")
    def _compute_can_access(self):
        for record in self:
            record.can_access = self._fully_access()

    active = fields.Boolean(string="Active", default=True)
    name = fields.Char(compute="_compute_name", store=True, readonly=False)
    date_from = fields.Date(default=lambda self: fields.Date.today().replace(day=1))
    date_to = fields.Date(
        default=lambda self: (date.today().replace(day=1) + timedelta(days=32)).replace(
            day=1
        )
        - timedelta(days=1)
    )
    policy_status = fields.Selection(
        selection=[
            ("open", "Sẵn sàng"),
            ("applying", "Đang Áp Dụng"),
            ("close", "Đã kết thúc"),
        ],
        default="open",
        string="Status",
    )
    product_attribute_ids = fields.Many2many("product.attribute")
    line_ids = fields.One2many(
        comodel_name="mv.warranty.discount.policy.line",
        inverse_name="warranty_discount_policy_id",
    )
    partner_ids = fields.Many2many(
        comodel_name="mv.discount.partner", domain=[("partner_id.is_agency", "=", True)]
    )

    def action_reset_to_open(self):
        self.ensure_one()

        if not self._fully_access():
            raise AccessError(
                "Bạn không có quyền thao tác, vui lòng liên hệ người có thẩm quyền!"
            )

        self.write({"policy_status": "open"})

    def action_apply(self):
        self.ensure_one()

        if not self._fully_access():
            raise AccessError(
                "Bạn không có quyền thao tác, vui lòng liên hệ người có thẩm quyền!"
            )

        if self.policy_status == "open":
            self.write({"policy_status": "applying"})

        return True

    def action_close(self):
        self.ensure_one()

        if not self._fully_access():
            raise AccessError(
                "Bạn không có quyền thao tác, vui lòng liên hệ người có thẩm quyền!"
            )

        if self.policy_status == "applying":
            self.write({"policy_status": "close"})

        return True

    @api.depends("date_from", "date_to")
    def _compute_name(self):
        for record in self:
            policy_name = "Chính sách chiết khấu kích hoạt"
            date_from = record.date_from
            date_to = record.date_to

            if date_from and date_to:
                if date_from.year == date_to.year:
                    if date_from.month == date_to.month:
                        record.name = (
                            f"{policy_name} (tháng {date_from.month}/{date_from.year})"
                        )
                    else:
                        record.name = f"{policy_name} (từ {date_from.month}/{date_from.year} đến {date_to.month}/{date_to.year})"
                else:
                    record.name = policy_name
            else:
                record.name = policy_name

    @api.onchange("date_from")
    def _onchange_date_from(self):
        if self.date_from:
            self.date_to = (self.date_from + timedelta(days=32)).replace(
                day=1
            ) - timedelta(days=1)

    @api.model_create_multi
    def create(self, vals_list):
        res = super(MvWarrantyDiscountPolicy, self).create(vals_list)

        # TODO: This method should be validated for every time create new record
        if res:
            for record in res:
                if not record.partner_ids:
                    partner_ids = self.env["mv.discount.partner"].search(
                        [("partner_id.is_agency", "=", True)]
                    )
                    record.partner_ids = [(6, 0, partner_ids.ids)]
                    for partner in partner_ids:
                        partner.write(
                            {"warranty_discount_policy_ids": [(4, record.id)]}
                        )

        return res

    def write(self, vals):
        res = super(MvWarrantyDiscountPolicy, self).write(vals)

        # TODO: This method should be validated for every time update current record
        if res:
            for record in self:
                if record.partner_ids:
                    for partner in record.partner_ids:
                        partner.write(
                            {"warranty_discount_policy_ids": [(6, 0, record.ids)]}
                        )

        return res

    @api.constrains("line_ids")
    def _limit_policy_conditions(self):
        for record in self:
            if len(record.line_ids) > 3:
                raise ValidationError(
                    _("Chính sách chiết khấu không được nhiều hơn 3 điều kiện!")
                )

    # =================================
    # CONSTRAINS Methods
    # =================================

    @api.constrains("date_from", "date_to")
    def _validate_already_exist_policy(self):
        for record in self:
            if record.date_from and record.date_to:
                record_exists = self.env["mv.warranty.discount.policy"].search_count(
                    [
                        ("id", "!=", record.id),
                        ("active", "=", True),
                        ("date_from", ">=", record.date_from),
                        ("date_to", "<=", record.date_to),
                    ]
                )
                if record_exists > 0:
                    raise ValidationError(
                        _("Chính sách này đã bị trùng, vui lòng kiểm tra lại!")
                    )

    # =================================
    # HELPER / PRIVATE Methods
    # =================================

    def _fully_access(self):
        access = (
            self.env.user.has_group(DISCOUNT_APPROVER)
            or self.env.user._is_admin()
            or self.env.user._is_system()
        )
        return access


class MvWarrantyDiscountPolicyLine(models.Model):
    _name = _description = "mv.warranty.discount.policy.line"
    _rec_name = "explanation"

    sequence = fields.Integer(required=True, default=1)
    warranty_discount_policy_id = fields.Many2one(
        comodel_name="mv.warranty.discount.policy",
        domain=[("active", "=", True)],
        readonly=True,
        help="Parent Model: mv.warranty.discount.policy",
    )
    currency_id = fields.Many2one(
        comodel_name="res.currency", default=lambda self: self.env.company.currency_id
    )
    quantity_from = fields.Integer("Số lượng Min", default=0)
    quantity_to = fields.Integer("Số lượng Max", default=0)
    discount_amount = fields.Monetary(
        "Số tiền chiết khấu", digits=(16, 2), currency_field="currency_id"
    )
    explanation = fields.Text("Diễn giải")
    explanation_code = fields.Char(
        "Diễn giải (Code)", compute="_compute_explanation_code", store=True
    )

    @api.depends("explanation")
    def _compute_explanation_code(self):
        for record in self:
            if record.explanation:
                record.explanation_code = convert_to_code(record.explanation)
            else:
                record.explanation_code = "_code_"


class MvComputeWarrantyDiscountPolicy(models.Model):
    _inherit = ["mail.thread"]
    _name = "mv.compute.warranty.discount.policy"
    _description = _("Compute Warranty Discount Policy")

    # ACCESS / RULE Fields:
    do_readonly = fields.Boolean("Readonly?", compute="_do_readonly")

    def _do_readonly(self):
        """
        Set the `do_readonly` field based on the state of the record.

        This method iterates over each record and sets the `do_readonly` field to `True`
        if the state is "done", otherwise sets it to `False`.

        :return: None
        """
        for rec in self:
            rec.do_readonly = rec.state == "done"

    # BASE Fields:
    month = fields.Selection(get_months())
    year = fields.Selection(get_years(), default=str(datetime.now().year))
    compute_date = fields.Datetime(compute="_compute_compute_date", store=True)
    name = fields.Char(compute="_compute_name", store=True)
    state = fields.Selection(
        selection=[("draft", "Nháp"), ("confirm", "Lưu"), ("done", "Đã Duyệt")],
        default="draft",
        readonly=True,
        tracking=True,
    )

    @api.depends("year", "month")
    def _compute_name(self):
        """
        Compute the name based on the month and year.

        This method sets the `name` field to "month/year" if both `month` and `year` are set.
        If either is not set, it uses the current month and year.

        :return: None
        """
        for rec in self:
            if rec.month and rec.year:
                rec.name = "{}/{}".format(str(rec.month), str(rec.year))
            else:
                dt = datetime.now().replace(day=1)
                rec.name = "{}/{}".format(str(dt.month), str(dt.year))

    # RELATION Fields:
    warranty_discount_policy_id = fields.Many2one(
        comodel_name="mv.warranty.discount.policy",
        domain=[("active", "=", True), ("policy_status", "=", "applying")],
    )
    line_ids = fields.One2many("mv.compute.warranty.discount.policy.line", "parent_id")

    @api.depends("year", "month")
    def _compute_compute_date(self):
        """
        Compute the `compute_date` based on the month and year.

        This method sets the `compute_date` field to the first day of the given month and year
        if both `month` and `year` are set. If either is not set, it uses the first day of the current month and year.

        :return: None
        """
        for rec in self:
            if rec.month and rec.year:
                rec.compute_date = datetime.now().replace(
                    day=1, month=int(rec.month), year=int(rec.year)
                )
            else:
                rec.compute_date = datetime.now().replace(day=1)

    # =================================
    # BUSINESS Methods
    # =================================

    def action_reset_to_draft(self):
        self.ensure_one()
        if self.state != "draft":
            self.state = "draft"
            self.line_ids.unlink()  # Remove all lines
            return True

    def action_calculate_discount_line(self):
        self.ensure_one()

        if not self.warranty_discount_policy_id:
            raise ValidationError("Chưa chọn Chính sách chiết khấu!")

        # Fetch all ticket with conditions at once
        tickets = self._fetch_tickets()
        if not tickets:
            raise UserError(
                "Hiện tại không có phiếu nào đã kích hoạt trong tháng {}/{}".format(
                    self.month, self.year
                )
            )

        # Get ticket has product move by [tickets]
        ticket_product_moves = self._fetch_ticket_product_moves(tickets)

        # Fetch partners at once
        partners = self._fetch_partners(ticket_product_moves)
        if not partners:
            raise UserError(
                "Không tìm thấy Đại lý đăng ký trong tháng {}/{}".format(
                    self.month, self.year
                )
            )

        # Calculate discount lines
        results = self._calculate_discount_lines(partners, ticket_product_moves)
        if not results:
            raise UserError(
                "Không có dữ liệu để tính chiết khấu cho tháng {}/{}".format(
                    self.month, self.year
                )
            )

        self.write({"line_ids": results, "state": "confirm"})

        # Create history line for discount
        if self.line_ids:
            for line in self.line_ids.filtered(lambda rec: rec.parent_id):
                self.create_history_line(
                    line,
                    "confirm",
                    "Chiết khấu kích hoạt bảo hành tháng %s đang chờ duyệt."
                    % line.parent_name,
                    line.total_amount_currency,
                )

    def action_done(self):
        if not self._access_approve():
            raise AccessError("Bạn không có quyền duyệt!")

        for record in self.filtered(lambda r: len(r.line_ids) > 0):
            for line in record.line_ids:
                partner = self.env["res.partner"].sudo().browse(line.partner_id.id)
                partner.action_update_discount_amount()
                helpdesk_tickets = line.helpdesk_ticket_product_moves_ids.mapped(
                    "helpdesk_ticket_id"
                )
                helpdesk_stage_done = self.env.ref(
                    "mv_website_helpdesk.warranty_stage_done"
                ).id
                stage_id = (
                    self.env["helpdesk.stage"]
                    .search(
                        [("id", "=", helpdesk_stage_done)],
                        limit=1,
                    )
                    .id
                )
                helpdesk_tickets.write({"stage_id": stage_id})

            # Create history line for discount
            for line in record.line_ids.filtered(lambda rec: rec.parent_id):
                self.create_history_line(
                    line,
                    "done",
                    "Chiết khấu kích hoạt bảo hành tháng %s đã được duyệt."
                    % line.parent_name,
                    line.total_amount_currency,
                )

            record.write({"state": "done"})

    def action_reset(self):
        if self.state == "confirm":

            # Create history line for discount
            for record in self:
                if record.line_ids:
                    for line in record.line_ids.filtered(lambda rec: rec.parent_id):
                        self.create_history_line(
                            line,
                            "cancel",
                            "Chiết khấu kích hoạt bảo hành tháng %s đã bị từ chối và đang chờ xem xét."
                            % line.parent_name,
                            line.total_amount_currency,
                        )

            self.action_reset_to_draft()

    def create_history_line(self, record, state, description, total_money):
        money_display = "{:,.2f}".format(total_money)
        is_waiting_approval = state == "confirm" and total_money > 0
        is_positive_money = state == "done" and total_money > 0
        is_negative_money = state == "cancel" and total_money > 0

        if state in ["confirm", "done"]:
            money_display = "+ " + money_display if total_money > 0 else money_display
        elif state == "cancel":
            money_display = "- " + money_display if total_money > 0 else money_display

        return self.env["mv.discount.partner.history"]._create_history_line(
            partner_id=record.sudo().partner_id.id,
            history_description=description,
            warranty_discount_policy_id=record.id,
            warranty_discount_policy_total_money=total_money,
            total_money=total_money,
            total_money_discount_display=money_display,
            is_waiting_approval=is_waiting_approval,
            is_positive_money=is_positive_money,
            is_negative_money=is_negative_money,
        )

    def _prepare_values_to_calculate_discount(self, partner, compute_date):
        self.ensure_one()
        return {
            "parent_id": self.id,
            "parent_compute_date": compute_date,
            "partner_id": partner.id,
            "currency_id": partner.company_id.sudo().currency_id.id
            or self.env.company.sudo().currency_id.id,
            "helpdesk_ticket_product_moves_ids": [],
            "product_activation_count": 0,
            "first_warranty_policy_requirement_id": False,
            "first_count": 0,
            "first_quantity_from": 0,
            "first_quantity_to": 0,
            "first_warranty_policy_money": 0,
            "first_warranty_policy_total_money": 0,
            "second_warranty_policy_requirement_id": False,
            "second_count": 0,
            "second_quantity_from": 0,
            "second_quantity_to": 0,
            "second_warranty_policy_money": 0,
            "second_warranty_policy_total_money": 0,
            "third_warranty_policy_requirement_id": False,
            "third_count": 0,
            "third_quantity_from": 0,
            "third_quantity_to": 0,
            "third_warranty_policy_money": 0,
            "third_warranty_policy_total_money": 0,
        }

    def _calculate_discount_lines(self, partners, ticket_product_moves):
        results = []
        policy_used = self.warranty_discount_policy_id
        compute_date = self.compute_date
        partners_mapped_with_policy = policy_used.partner_ids.mapped("partner_id").ids
        partners_to_compute_discount = partners.filtered(
            lambda p: p.is_agency
            and p.id in partners_mapped_with_policy
            or p.parent_id.is_agency
            and p.parent_id.id in partners_mapped_with_policy
        )

        for partner in partners_to_compute_discount:
            # Prepare values to calculate discount
            if not partner.is_agency:
                vals = self._prepare_values_to_calculate_discount(
                    partner.parent_id, compute_date
                )
            else:
                vals = self._prepare_values_to_calculate_discount(partner, compute_date)

            partner_tickets_registered = ticket_product_moves.filtered(
                lambda t: t.partner_id.id == partner.id
                or t.partner_id.parent_id.id == partner.id
            )
            vals["helpdesk_ticket_product_moves_ids"] += partner_tickets_registered.ids
            vals["product_activation_count"] = len(
                list(set(partner_tickets_registered))
            )

            context_lines = dict(self.env.context or {})

            # ========= First Condition Warranty Policy =========
            first_count = 0
            first_policy_code = (
                context_lines.get("first_policy_code") or "rim_lower_and_equal_16"
            )
            first_warranty_policy = self._fetch_warranty_policy(first_policy_code)
            vals["first_warranty_policy_requirement_id"] = first_warranty_policy.id
            vals["first_quantity_from"] = first_warranty_policy.quantity_from
            vals["first_quantity_to"] = first_warranty_policy.quantity_to
            vals["first_warranty_policy_money"] = (
                first_warranty_policy.discount_amount or 0
            )
            # ========= Second Condition Warranty Policy =========
            second_count = 0
            second_policy_code = (
                context_lines.get("second_policy_code") or "rim_greater_and_equal_17"
            )
            second_warranty_policy = self._fetch_warranty_policy(second_policy_code)
            vals["second_warranty_policy_requirement_id"] = second_warranty_policy.id
            vals["second_quantity_from"] = second_warranty_policy.quantity_from
            vals["second_quantity_to"] = second_warranty_policy.quantity_to
            vals["second_warranty_policy_money"] = (
                second_warranty_policy.discount_amount or 0
            )
            # ========= Third Condition Warranty Policy =========
            third_count = 0
            third_policy_code = context_lines.get("third_policy_code") or None
            third_warranty_policy = self._fetch_warranty_policy(
                third_policy_code,
                [
                    ("sequence", "=", 3),
                    (
                        "explanation_code",
                        "not in",
                        [first_policy_code, second_policy_code],
                    ),
                ],
            )
            vals["third_warranty_policy_requirement_id"] = third_warranty_policy.id
            vals["third_quantity_from"] = third_warranty_policy.quantity_from
            vals["third_quantity_to"] = third_warranty_policy.quantity_to
            vals["third_warranty_policy_money"] = (
                third_warranty_policy.discount_amount or 0
            )

            for ticket_product_move in partner_tickets_registered:
                product_tmpl = self._fetch_product_template(
                    ticket_product_move.product_id.product_tmpl_id
                )
                for product in product_tmpl:
                    product_tmpl_attribute_lines = (
                        self._fetch_product_template_attribute_lines(
                            policy_used, product
                        )
                    )
                    if not product_tmpl_attribute_lines:
                        raise MissingError(
                            "Không tìm thấy thông tin thuộc tính sản phẩm!"
                        )

                    product_tmpl_attribute_values = (
                        self._fetch_product_template_attribute_values(
                            product_tmpl_attribute_lines
                        )
                    )
                    product_attribute_values = self._fetch_product_attribute_values(
                        policy_used, product_tmpl_attribute_values
                    )

                    for attribute in product_attribute_values:
                        # ========= First Condition (Product has RIM <= 16) =========
                        if float(attribute.name) <= float(
                            first_warranty_policy.quantity_to
                        ):
                            first_count += 1
                        # ========= Second Condition (Product has RIM >= 17) =========
                        elif float(attribute.name) >= float(
                            second_warranty_policy.quantity_from
                        ):
                            second_count += 1

            vals["first_count"] = first_count
            vals["first_warranty_policy_total_money"] = (
                first_warranty_policy.discount_amount * first_count
            )
            vals["second_count"] = second_count
            vals["second_warranty_policy_total_money"] = (
                second_warranty_policy.discount_amount * second_count
            )

            results.append((0, 0, vals))

        return results

    def _fetch_tickets(self):
        try:
            date_from, date_to = self._get_dates(
                self.compute_date, self.month, self.year
            )

            # Cache the stage references to avoid multiple lookups
            stage_new_id = self.env.ref("mv_website_helpdesk.warranty_stage_new").id
            stage_done_id = self.env.ref("mv_website_helpdesk.warranty_stage_done").id

            # Define the domain for search
            domain = [
                ("helpdesk_ticket_product_move_ids", "!=", False),
                ("ticket_type_id.code", "in", [SUB_DEALER_CODE, END_USER_CODE]),
                ("stage_id", "in", [stage_new_id, stage_done_id]),
                ("create_date", ">=", date_from),
                ("create_date", "<", date_to),
            ]

            # Perform the search
            return self.env["helpdesk.ticket"].search(domain)

        except ValueError as ve:
            _logger.error(f"Value error in fetching tickets: {ve}")
        except self.env["helpdesk.ticket"]._exceptions.AccessError as ae:
            _logger.error(f"Access error in fetching tickets: {ae}")
        except Exception as e:
            _logger.error(f"Unexpected error in fetching tickets: {e}")

        # Return an empty recordset in case of an error
        return self.env["helpdesk.ticket"]

    def _fetch_ticket_product_moves(self, tickets):
        if not tickets:
            return self.env["mv.helpdesk.ticket.product.moves"]

        try:
            return self.env["mv.helpdesk.ticket.product.moves"].search(
                [
                    ("helpdesk_ticket_id", "in", tickets.ids),
                    ("product_activate_twice", "=", False),
                ]
            )
        except Exception as e:
            _logger.error(f"Failed to fetch ticket product moves: {e}")
            return self.env["mv.helpdesk.ticket.product.moves"]

    def _fetch_partners(self, ticket_product_moves):
        try:
            if ticket_product_moves:
                return (
                    self.env["res.partner"]
                    .sudo()
                    .browse(ticket_product_moves.mapped("partner_id").ids)
                )
        except Exception as e:
            _logger.error(f"Failed to fetch partners: {e}")
            return self.env["res.partner"]

    def _fetch_warranty_policy(self, policy_code, domain=[]):
        try:
            policy_domain = domain
            if policy_code and not domain:
                policy_domain = [("explanation_code", "=", policy_code)]

            return self.env["mv.warranty.discount.policy.line"].search(
                policy_domain, limit=1
            )
        except Exception as e:
            _logger.error(f"Failed to fetch warranty policy: {e}")
            return self.env["mv.warranty.discount.policy.line"]

    def _fetch_product_template(self, products):
        try:
            if products:
                return self.env["product.template"].search(
                    [("id", "in", products.ids), ("detailed_type", "=", "product")]
                )
        except Exception as e:
            _logger.error(f"Failed to fetch product template: {e}")
            return self.env["product.template"]

    def _fetch_product_template_attribute_lines(self, policy_used, products):
        try:
            if products:
                return self.env["product.template.attribute.line"].search(
                    [
                        ("product_tmpl_id", "in", products.ids),
                        ("attribute_id", "in", policy_used.product_attribute_ids.ids),
                    ]
                )
        except Exception as e:
            _logger.error(f"Failed to fetch product template attribute lines: {e}")
            return self.env["product.template.attribute.line"]

    def _fetch_product_template_attribute_values(self, products):
        try:
            if products:
                return self.env["product.template.attribute.value"].search(
                    [
                        ("attribute_line_id", "in", products.ids),
                        ("ptav_active", "=", True),
                    ]
                )
        except Exception as e:
            _logger.error(f"Failed to fetch product template attribute values: {e}")
            return self.env["product.template.attribute.value"]

    def _fetch_product_attribute_values(self, policy_used, products):
        try:
            if products and policy_used:
                return self.env["product.attribute.value"].search(
                    [
                        (
                            "id",
                            "in",
                            products.mapped("product_attribute_value_id")
                            .filtered(
                                lambda v: v.attribute_id.id
                                in policy_used.product_attribute_ids.ids
                            )
                            .ids,
                        )
                    ]
                )
        except Exception as e:
            _logger.error(f"Failed to fetch product attribute values: {e}")
            return self.env["product.attribute.value"]

    # =================================
    # ORM Methods
    # =================================

    def unlink(self):
        """
        Unlink the current record after validating and cleaning up related records.

        This method ensures that the policy is not in the "done" state before unlinking.
        It also removes any `mv.compute.warranty.discount.policy.line` records with `parent_id` set to `False`.

        :return: bool: Result of the unlink operation.
        """
        self._validate_policy_done_not_unlink()
        self.env["mv.compute.warranty.discount.policy.line"].search(
            [("parent_id", "=", False)]
        ).unlink()

        return super(MvComputeWarrantyDiscountPolicy, self).unlink()

    # =================================
    # CONSTRAINS / VALIDATION Methods
    # =================================

    def _validate_policy_done_not_unlink(self):
        for rec in self:
            if rec.state == "done":
                raise UserError(
                    f"Phần tính toán chiết khấu cho tháng {rec.month}/{rec.year} đã được Duyệt. Không thể xoá! "
                )

    @api.constrains("warranty_discount_policy_id", "month", "year")
    def _validate_discount_policy_already_exist(self):
        for record in self:
            if record.warranty_discount_policy_id and record.month and record.year:
                record_exists = self.env[
                    "mv.compute.warranty.discount.policy"
                ].search_count(
                    [
                        ("id", "!=", record.id),
                        (
                            "warranty_discount_policy_id",
                            "=",
                            record.warranty_discount_policy_id.id,
                        ),
                        ("month", "=", record.month),
                        ("year", "=", record.year),
                    ]
                )
                if record_exists > 0:
                    raise ValidationError(
                        f"Chính sách của {record.month}/{record.year} đã được tạo hoặc đã được tính toán rồi!"
                    )

    @api.constrains(
        "compute_date",
        "warranty_discount_policy_id.date_from",
        "warranty_discount_policy_id.date_to",
    )
    def _validate_time_frame_of_discount_policy(self):
        for record in self:
            if record.warranty_discount_policy_id and record.compute_date:
                policy = record.warranty_discount_policy_id
                if not policy.date_from <= record.compute_date.date() <= policy.date_to:
                    raise ValidationError(
                        "Tháng cần tính toán phải nằm trong khoảng thời gian quy định của chính sách!"
                    )

    # =================================
    # HELPER / PRIVATE Methods
    # =================================

    def _get_dates(self, report_date, month, year):
        """
        Computes the start and end dates of a given month and year.

        Args:
            month (str): The target month.
            year (str): The target year.

        Returns:
            tuple: A tuple containing the start and end dates of the given month and year.
        """
        try:
            # Compute date_from
            date_from = report_date.replace(
                day=1,
                month=int(month),
                year=int(year),
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

            # Compute date_to by adding one month and then subtracting one day
            date_to = date_from + relativedelta(months=1)

            return date_from, date_to
        except Exception as e:
            _logger.error("Failed to compute dates: %s", e)
            return None, None

    def _access_approve(self):
        return self.env.user.has_group(DISCOUNT_APPROVER)

    # =================================
    # REPORT Action/Data
    # =================================

    @api.model
    def format_value(self, amount, currency=False, blank_if_zero=False):
        """Format amount to have a monetary display (with a currency symbol).
        E.g: 1000 => 1000.0 $

        :param amount:          A number.
        :param currency:        An optional res.currency record.
        :param blank_if_zero:   An optional flag forcing the string to be empty if amount is zero.
        :return:                The formatted amount as a string.
        """
        currency_id = currency or self.env.company.currency_id
        if currency_id.is_zero(amount):
            if blank_if_zero:
                return ""
            # don't print -0.0 in reports
            amount = abs(amount)

        if self.env.context.get("no_format"):
            return amount
        return formatLang(self.env, amount, currency_obj=currency_id)

    def print_report(self):
        if not self:
            raise UserError(_("No data to generate the report for."))

        months = set(self.mapped("month"))
        if len(months) > 1:
            raise UserError(_("Only export report in ONE MONTH!"))

        self._get_discount_lines(self.warranty_discount_policy_id, self.compute_date)

        # DOWNLOAD Report Data
        file_content, file_name = self._generate_excel_data(
            self.warranty_discount_policy_id, self.compute_date
        )

        # REMOVE All Excel Files by file_content:
        self._remove_old_attachments()

        # NEW Attachment to download
        new_attachment = self._create_new_attachment(file_content, file_name)
        if len(new_attachment) == 1:
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{new_attachment[0].id}?download=true",
                "target": "self",
            }

    def _remove_old_attachments(self):
        attachments_to_remove = self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("create_uid", "=", self.env.uid),
                ("create_date", "<", fields.Datetime.now()),
                ("name", "ilike", "Moveoplus-Warranty-Discount-%"),
            ]
        )
        if attachments_to_remove:
            attachments_to_remove.unlink()

    def _create_new_attachment(self, file_content, file_name):
        return self.env["ir.attachment"].create(
            {
                "name": file_name,
                "datas": base64.b64encode(file_content),
                "type": "binary",
                "res_model": self._name,
                "res_id": self.id,
            }
        )

    def _get_policy_attributes_values(self, policy):
        try:
            # Initialize an empty list to store the attribute values
            attribute_values = []

            # Iterate over the product attributes of the policy
            for attribute in policy.product_attribute_ids:
                # Get the attribute values, convert them to float, sort them in ascending order and add them to the list
                sorted_values = sorted(
                    [float(value.name) for value in attribute.value_ids], reverse=False
                )
                for value in sorted_values:
                    attribute_values.append(
                        str(int(value) if value.is_integer() else value)
                    )

            return attribute_values

        except ValueError as value_error:
            _logger.error("Value error in fetching attribute values: %s", value_error)
            raise UserError(
                _(
                    "Invalid attribute value. Please ensure all attribute values are numbers."
                )
            )
        except Exception as general_error:
            _logger.error(
                "Unexpected error in fetching attribute values: %s", general_error
            )
            raise UserError(_("An unexpected error occurred. Please try again."))

    def _get_discount_lines(self, policy, report_date):
        ComputeLine_env = self.env["mv.compute.warranty.discount.policy.line"]
        ComputeLine_env.flush_model()
        lines = []

        # Fetch policy lines
        policy_lines = ComputeLine_env.search([("parent_id", "=", self.id)], order="id")

        # Fetch product attributes
        attributes = self.env["product.attribute"].browse(
            policy.product_attribute_ids.ids
        )

        for line in policy_lines:
            line_dict = {
                "partner": line.partner_id.name,
                "grand_total": line.product_activation_count,
                "first_policy_explanation": line.first_warranty_policy_requirement_id.explanation,
                "first_count": line.first_count,
                "first_warranty_policy_money": line.first_warranty_policy_money,
                "first_warranty_policy_total_money": line.first_warranty_policy_total_money,
                "second_policy_explanation": line.second_warranty_policy_requirement_id.explanation,
                "second_count": line.second_count,
                "second_warranty_policy_money": line.second_warranty_policy_money,
                "second_warranty_policy_total_money": line.second_warranty_policy_total_money,
                "total_amount_currency": line.total_amount_currency,
            }

            # Fetch attribute values
            attributes_values = []
            for attribute in attributes:
                for value in sorted(
                    [float(val.name) for val in attribute.value_ids], reverse=False
                ):
                    attributes_values.append(
                        (
                            f"{attribute.attribute_code}_{str(int(value) if value.is_integer() else value).replace('.', '_')}",
                            str(int(value) if value.is_integer() else value),
                        )
                    )
                    line_dict.update(
                        {
                            f"{attribute.attribute_code}_{str(int(value) if value.is_integer() else value).replace('.', '_')}": {
                                "name": str(
                                    int(value) if value.is_integer() else value
                                ),
                                "count": 0,
                            }
                        }
                    )

            # Fetch attribute values for each product
            for ticket_move in line.helpdesk_ticket_product_moves_ids:
                line_product_att_values = (
                    ticket_move.product_id.product_tmpl_id.attribute_line_ids.filtered(
                        lambda r: r.attribute_id
                        and r.attribute_id.attribute_code
                        in attributes.mapped("attribute_code")
                    ).value_ids.mapped("name")
                )
                for value in attributes_values:
                    if value[1] in line_product_att_values:
                        line_dict[value[0]]["count"] += 1

            lines.append(line_dict)

        return lines

    def _generate_excel_data(self, policy, report_date):
        self.ensure_one()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(
            output,
            {
                "in_memory": True,
                "strings_to_formulas": False,
            },
        )
        sheet = workbook.add_worksheet()
        discount_lines = self._get_discount_lines(policy, report_date)
        attributes_values = self._get_policy_attributes_values(policy)

        # ############# [SETUP] #############
        base_format = {
            "bold": True,
            "font_name": "Arial",
            "font_size": 11,
            "align": "center",
            "valign": "vcenter",
            "border": True,
            "border_color": "black",
        }

        attribute_header_from_col = 1  # Column B (B is the 2nd column, 0-indexed)
        attribute_header_to_col = attribute_header_from_col + len(attributes_values)
        grand_total_col = attribute_header_to_col
        first_policy_count_col = attribute_header_to_col + 1
        first_policy_discount_money_col = attribute_header_to_col + 2
        second_policy_count_col = attribute_header_to_col + 3
        second_policy_discount_money_col = attribute_header_to_col + 4
        total_discount_amount_col = attribute_header_to_col + 5

        sheet.set_row(0, 30)
        sheet.set_row(1, 20)
        sheet.set_row(2, 30)
        sheet.set_column("A:A", 50)
        sheet.set_column(attribute_header_from_col, attribute_header_to_col, 5)
        sheet.set_column(grand_total_col, grand_total_col, 7)
        sheet.set_column(first_policy_count_col, first_policy_count_col, 10)
        sheet.set_column(
            first_policy_discount_money_col, first_policy_discount_money_col, 10
        )
        sheet.set_column(second_policy_count_col, second_policy_count_col, 10)
        sheet.set_column(
            second_policy_discount_money_col, second_policy_discount_money_col, 10
        )
        sheet.set_column(total_discount_amount_col, total_discount_amount_col, 15)

        # ############# [HEADER] #############

        # ========= [ROW-1] =========

        # => "Chi tiết chiết khấu kích hoạt của Đại Lý trong tháng {month/year}"
        base_title_format_A1 = base_format.copy()
        base_title_format_A1.update({"border": False})
        sheet.merge_range(
            0,
            0,
            0,
            attribute_header_to_col + 5,
            "",
            workbook.add_format(base_title_format_A1),
        )
        sheet.write_rich_string(
            "A1",
            *[
                "Chi tiết chiết khấu kích hoạt của Đại Lý trong tháng ",
                workbook.add_format(
                    {
                        "font_name": "Arial",
                        "font_size": 11,
                        "color": "red",
                        "bold": True,
                    }
                ),
                "{}/{}".format(report_date.month, report_date.year),
            ],
            workbook.add_format(base_title_format_A1),
        )

        # ========= [ROW-2] =========

        # => "COUNTA of Serial Number"
        base_title_format_A2 = base_format.copy()
        base_title_format_A2.update(
            {
                "font_size": 10,
                "bg_color": "#C4DCE0",
                "border_color": "#D3D3D3",
                "align": "left",
                "italic": True,
            }
        )
        sheet.write(
            "A2", "COUNTA of Serial Number", workbook.add_format(base_title_format_A2)
        )

        # => "RIM"
        base_title_format_B2 = base_format.copy()
        base_title_format_B2.update(
            {
                "font_size": 10,
                "bg_color": "#C4DCE0",
                "border_color": "#D3D3D3",
                "align": "left",
                "italic": True,
            }
        )
        sheet.merge_range(
            1,
            attribute_header_from_col,
            1,
            attribute_header_to_col,
            "Rim",
            workbook.add_format(base_title_format_B2),
        )

        # => "First Policy Explanation"
        base_title_format_first_policy = base_format.copy()
        base_title_format_first_policy.update(
            {"font_size": 10, "font_color": "#FEFDED", "bg_color": "#430A5D"}
        )
        sheet.merge_range(
            1,
            first_policy_count_col,
            1,
            first_policy_discount_money_col,
            "{} ({})".format(
                policy.line_ids[0].explanation, int(policy.line_ids[0].discount_amount)
            ),
            workbook.add_format(base_title_format_first_policy),
        )

        # => "Second Policy Explanation"
        base_title_format_second_policy = base_format.copy()
        base_title_format_second_policy.update(
            {"font_size": 10, "font_color": "#FEFDED", "bg_color": "#FFC700"}
        )
        sheet.merge_range(
            1,
            second_policy_count_col,
            1,
            second_policy_discount_money_col,
            "{} ({})".format(
                policy.line_ids[1].explanation, int(policy.line_ids[1].discount_amount)
            ),
            workbook.add_format(base_title_format_second_policy),
        )

        # => "TỔNG"
        base_title_format_total_discount_amount = base_format.copy()
        base_title_format_total_discount_amount.update(
            {
                "font_size": 10,
                "font_color": "#FEFDED",
                "bg_color": "#9BCF53",
            }
        )
        sheet.write(
            1,
            total_discount_amount_col,
            "TỔNG",
            workbook.add_format(base_title_format_total_discount_amount),
        )

        # ========= [ROW-3] =========

        # => "Đại lý"
        base_title_format_A3 = base_format.copy()
        base_title_format_A3.update(
            {
                "font_size": 10,
                "bg_color": "#C4DCE0",
                "border_color": "#D3D3D3",
                "align": "left",
                "italic": True,
                "bottom_color": "#577B8D",
            }
        )
        sheet.write("A3", "Đại lý", workbook.add_format(base_title_format_A3))

        # => "Values of RIM"
        base_title_format_rim_values = base_format.copy()
        base_title_format_rim_values.update(
            {"font_size": 10, "bg_color": "#577B8D", "border_color": "#D3D3D3"}
        )
        for col, value in enumerate(attributes_values):
            value_format = float(value)
            sheet.write(
                2,
                attribute_header_from_col + col,
                value_format,
                workbook.add_format(base_title_format_rim_values),
            )

        # => "Grand Total"
        base_title_format_grand_total = base_format.copy()
        base_title_format_grand_total.update(
            {
                "font_size": 10,
                "bg_color": "#577B8D",
                "border_color": "#D3D3D3",
                "text_wrap": True,
            }
        )
        sheet.write(
            2,
            grand_total_col,
            "Grand Total",
            workbook.add_format(base_title_format_grand_total),
        )

        # => "First Policy Explanation - Count"
        sheet.write(
            2,
            first_policy_count_col,
            "Số lượng",
            workbook.add_format(base_title_format_first_policy.copy()),
        )
        # => "First Policy Explanation - Discount Money"
        sheet.write(
            2,
            first_policy_discount_money_col,
            "Số tiền",
            workbook.add_format(base_title_format_first_policy.copy()),
        )

        # => "Second Policy Explanation - Count"
        sheet.write(
            2,
            second_policy_count_col,
            "Số lượng",
            workbook.add_format(base_title_format_second_policy.copy()),
        )
        # => "Second Policy Explanation - Discount Money"
        sheet.write(
            2,
            second_policy_discount_money_col,
            "Số tiền",
            workbook.add_format(base_title_format_second_policy.copy()),
        )

        # => "Total Discount Money"
        sheet.write(
            2,
            total_discount_amount_col,
            "THƯỞNG",
            workbook.add_format(base_title_format_total_discount_amount.copy()),
        )

        # ############# [BODY] #############

        base_format_for_body = base_format.copy()
        base_format_for_body.update({"bold": False, "font_size": 10})
        base_format_for_partner = base_format.copy()
        base_format_for_partner.update(
            {
                "bold": False,
                "font_size": 10,
                "align": "left",
                "text_wrap": True,
                "border_color": "#D3D3D3",
            }
        )
        base_format_attribute_value = base_format_for_body.copy()
        base_format_attribute_value.update({"border_color": "#D3D3D3"})
        base_format_hide_value = base_format_attribute_value.copy()
        base_format_hide_value.update({"bg_color": "#DDDDDD"})
        base_title_format_grand_total_detail = base_format_for_body.copy()
        base_title_format_grand_total_detail.update({"border_color": "#D3D3D3"})
        base_format_for_total = base_format.copy()
        base_format_for_total.update(
            {
                "bold": False,
                "font_size": 10,
                "align": "right",
                "num_format": "#,##0.00",
            }
        )

        column_headers = list(discount_lines[0].keys())
        for row, data in enumerate(discount_lines, start=3):
            attribute_col = 1
            for col, key in enumerate(column_headers):
                if key == "partner":
                    sheet.write(
                        row,
                        col,
                        data[key],
                        workbook.add_format(base_format_for_partner),
                    )
                elif key.startswith("rim_"):
                    if data[key]["count"] > 0:
                        sheet.write(
                            row,
                            attribute_col,
                            data[key]["count"],
                            workbook.add_format(base_format_attribute_value),
                        )
                    else:
                        sheet.write(
                            row,
                            attribute_col,
                            "",
                            workbook.add_format(base_format_hide_value),
                        )
                    attribute_col += 1
                elif key in [
                    "grand_total",
                    "first_count",
                    "first_warranty_policy_total_money",
                    "second_count",
                    "second_warranty_policy_total_money",
                    "total_amount_currency",
                ]:
                    sheet.write(
                        row,
                        grand_total_col,
                        data["grand_total"],
                        workbook.add_format(base_title_format_grand_total_detail),
                    )
                    sheet.write(
                        row,
                        first_policy_count_col,
                        data["first_count"],
                        workbook.add_format(base_format_for_body),
                    )
                    sheet.write(
                        row,
                        first_policy_discount_money_col,
                        data["first_warranty_policy_total_money"],
                        workbook.add_format(base_format_for_total),
                    )
                    sheet.write(
                        row,
                        second_policy_count_col,
                        data["second_count"],
                        workbook.add_format(base_format_for_body),
                    )
                    sheet.write(
                        row,
                        second_policy_discount_money_col,
                        data["second_warranty_policy_total_money"],
                        workbook.add_format(base_format_for_total),
                    )
                    sheet.write(
                        row,
                        total_discount_amount_col,
                        data["total_amount_currency"],
                        workbook.add_format(base_format_for_total),
                    )

        # ############# [FOOTER] #############

        base_title_format_partner_last = base_format.copy()
        base_title_format_partner_last.update(
            {
                "font_size": 10,
                "bg_color": "#C4DCE0",
                "align": "left",
                "top": 6,
                "top_color": "black",
                "border_color": "#D3D3D3",
            }
        )
        base_title_format_attribute_value_last = base_format.copy()
        base_title_format_attribute_value_last.update(
            {
                "font_size": 10,
                "bg_color": "#C4DCE0",
                "top": 6,
                "top_color": "black",
                "border_color": "#D3D3D3",
            }
        )
        base_title_format_grand_total_last = base_format.copy()
        base_title_format_grand_total_last.update(
            {
                "font_size": 10,
                "bg_color": "#C4DCE0",
                "top": 6,
                "top_color": "black",
                "border_color": "#D3D3D3",
            }
        )
        base_format_for_sum_last = base_format.copy()
        base_format_for_sum_last.update({"font_size": 10, "bg_color": "#9BCF53"})
        base_format_for_sum_last_total = base_format_for_sum_last.copy()
        base_format_for_sum_last_total.update(
            {
                "align": "right",
                "num_format": "#,##0.00",
                "bg_color": "#9BCF53",
            }
        )

        column_headers = list(discount_lines[0].keys())
        attribute_col = 1
        for col, key in enumerate(column_headers):
            if key == "partner":
                sheet.write(
                    len(discount_lines) + 3,
                    0,
                    "Grand Total",
                    workbook.add_format(base_title_format_partner_last),
                )
            elif key.startswith("rim_"):
                sheet.write(
                    len(discount_lines) + 3,
                    attribute_col,
                    sum(
                        discount_lines[i][key]["count"]
                        for i in range(len(discount_lines))
                    ),
                    workbook.add_format(base_title_format_attribute_value_last),
                )
                attribute_col += 1
            elif key in [
                "grand_total",
                "first_count",
                "first_warranty_policy_total_money",
                "second_count",
                "second_warranty_policy_total_money",
                "total_amount_currency",
            ]:
                sheet.write(
                    len(discount_lines) + 3,
                    grand_total_col,
                    sum(
                        discount_lines[i]["grand_total"]
                        for i in range(len(discount_lines))
                    ),
                    workbook.add_format(base_title_format_grand_total_last),
                )
                sheet.write(
                    len(discount_lines) + 3,
                    first_policy_count_col,
                    sum(
                        discount_lines[i]["first_count"]
                        for i in range(len(discount_lines))
                    ),
                    workbook.add_format(base_format_for_sum_last),
                )
                sheet.write(
                    len(discount_lines) + 3,
                    first_policy_discount_money_col,
                    sum(
                        discount_lines[i]["first_warranty_policy_total_money"]
                        for i in range(len(discount_lines))
                    ),
                    workbook.add_format(base_format_for_sum_last_total),
                )
                sheet.write(
                    len(discount_lines) + 3,
                    second_policy_count_col,
                    sum(
                        discount_lines[i]["second_count"]
                        for i in range(len(discount_lines))
                    ),
                    workbook.add_format(base_format_for_sum_last),
                )
                sheet.write(
                    len(discount_lines) + 3,
                    second_policy_discount_money_col,
                    sum(
                        discount_lines[i]["second_warranty_policy_total_money"]
                        for i in range(len(discount_lines))
                    ),
                    workbook.add_format(base_format_for_sum_last_total),
                )
                sheet.write(
                    len(discount_lines) + 3,
                    total_discount_amount_col,
                    sum(
                        discount_lines[i]["total_amount_currency"]
                        for i in range(len(discount_lines))
                    ),
                    workbook.add_format(base_format_for_sum_last_total),
                )

        workbook.close()
        output.seek(0)

        file_name = "Moveoplus-Warranty-Discount-Detail_%s-%s.xlsx" % (
            report_date.month,
            report_date.year,
        )
        return output.read(), file_name.replace("-", "_")


class MvComputeWarrantyDiscountPolicyLine(models.Model):
    _name = "mv.compute.warranty.discount.policy.line"
    _description = _("Compute Warranty Discount (%) Line for Partner")

    currency_id = fields.Many2one(
        "res.currency", compute="_get_company_currency", store=True
    )
    parent_id = fields.Many2one(
        "mv.compute.warranty.discount.policy",
        domain=[("active", "=", True)],
        readonly=True,
    )
    parent_name = fields.Char("Name", compute="_compute_parent_name", store=True)
    parent_compute_date = fields.Datetime(readonly=True)
    parent_state = fields.Selection(related="parent_id.state", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    helpdesk_ticket_product_moves_ids = fields.Many2many(
        "mv.helpdesk.ticket.product.moves",
        "compute_warranty_discount_policy_ticket_product_moves_rel",
        readonly=True,
        context={"create": False, "edit": False},
    )
    product_activation_count = fields.Integer(default=0)
    first_warranty_policy_requirement_id = fields.Many2one(
        "mv.warranty.discount.policy.line", readonly=True
    )
    first_count = fields.Integer()
    first_quantity_from = fields.Integer()
    first_quantity_to = fields.Integer()
    first_warranty_policy_money = fields.Monetary(
        digits=(16, 2), currency_field="currency_id"
    )
    first_warranty_policy_total_money = fields.Monetary(
        digits=(16, 2), currency_field="currency_id"
    )
    second_warranty_policy_requirement_id = fields.Many2one(
        "mv.warranty.discount.policy.line", readonly=True
    )
    second_count = fields.Integer()
    second_quantity_from = fields.Integer()
    second_quantity_to = fields.Integer()
    second_warranty_policy_money = fields.Monetary(
        digits=(16, 2), currency_field="currency_id"
    )
    second_warranty_policy_total_money = fields.Monetary(
        digits=(16, 2), currency_field="currency_id"
    )
    third_warranty_policy_requirement_id = fields.Many2one(
        "mv.warranty.discount.policy.line", readonly=True
    )
    third_count = fields.Integer()
    third_quantity_from = fields.Integer()
    third_quantity_to = fields.Integer()
    third_warranty_policy_money = fields.Monetary(
        digits=(16, 2), currency_field="currency_id"
    )
    third_warranty_policy_total_money = fields.Monetary(
        digits=(16, 2), currency_field="currency_id"
    )
    total_amount_currency = fields.Monetary(
        compute="_compute_total",
        store=True,
        digits=(16, 2),
        currency_field="currency_id",
    )

    def _get_company_currency(self):
        for rec in self:
            company = rec.partner_id.company_id or self.env.company
            rec.currency_id = company.sudo().currency_id

    @api.depends("parent_compute_date")
    def _compute_parent_name(self):
        for rec in self:
            if rec.parent_compute_date:
                rec.parent_name = "{}/{}".format(
                    str(rec.parent_compute_date.month),
                    str(rec.parent_compute_date.year),
                )
            else:
                dt = datetime.now().replace(day=1)
                rec.parent_name = "{}/{}".format(str(dt.month), str(dt.year))

    @api.depends(
        "first_warranty_policy_total_money",
        "second_warranty_policy_total_money",
        "third_warranty_policy_total_money",
    )
    def _compute_total(self):
        for rec in self:
            rec.total_amount_currency = (
                rec.first_warranty_policy_total_money
                + rec.second_warranty_policy_total_money
                + rec.third_warranty_policy_total_money
            )
