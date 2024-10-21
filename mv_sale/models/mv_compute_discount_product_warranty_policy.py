# -*- coding: utf-8 -*-
import logging
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT,
)

POLICY_APPROVER = "mv_sale.group_mv_compute_discount_approver"
SUB_DEALER_CODE = "kich_hoat_bao_hanh_dai_ly"
END_USER_CODE = "kich_hoat_bao_hanh_nguoi_dung_cuoi"
TICKET_PRODUCT_MOVE_MODEL = "mv.helpdesk.ticket.product.moves"


def get_years():
    return [(str(i), str(i)) for i in range(2000, datetime.now().year + 1)]


def get_months():
    return [(str(i), str(i)) for i in range(1, 13)]


def get_current_date_string():
    dt = datetime.now().replace(day=1)
    return "{}/{}".format(str(dt.month), str(dt.year))


class MvComputeDiscountProductWarrantyPolicy(models.Model):
    _name = "mv.compute.discount.product.warranty.policy"
    _description = "CHIẾT KHẤU THƯỞNG KÍCH HOẠT THEO SẢN PHẨM cho Đại lý"
    _inherit = ["mail.thread"]

    @staticmethod
    def _has_approval_access(env):
        """
        Check if the user has approval access.

        :param env: Environment context to access user groups.
        :return: True/False
        """
        return env.user.has_group(POLICY_APPROVER)

    def set_readonly_fields(self):
        """
        Set the `do_readonly` field based on the state of the record.

        This method iterates over each record and sets the `do_readonly`
        field to `True` if the state is "done", otherwise sets it to `False`.

        :return: None
        """
        for record in self:
            self._set_single_record_readonly(record)

    def _set_single_record_readonly(self, record):
        """
        Set the `do_readonly` field for a single record based on its state.

        :param record: the record object
        :return: None
        """
        record.do_readonly = record.state == "done"

    name = fields.Char(
        compute="_compute_name_from_date_parts",
        default="New",
        store=True,
    )
    year = fields.Selection(get_years(), "Năm", default=str(date.today().year))
    month = fields.Selection(get_months(), "Tháng", default=str(date.today().month))
    report_date = fields.Datetime(compute="_compute_report_date", store=True)
    approved_date = fields.Datetime(readonly=True)
    state = fields.Selection(
        [("draft", "Nháp"), ("confirm", "Lưu"), ("done", "Duyệt")],
        "Trạng thái",
        default="draft",
        tracking=True,
        readonly=True,
    )
    discount_product_warranty_policy_id = fields.Many2one(
        "mv.discount.product.warranty.policy",
        required=True,
        domain=[("active", "=", True), ("policy_status", "=", "applying")],
        default=lambda self: self.env["mv.discount.product.warranty.policy"].search(
            [("active", "=", True), ("policy_status", "=", "applying")], limit=1
        ),
    )
    line_ids = fields.One2many(
        "mv.compute.discount.product.warranty.policy.line",
        "parent_id",
        "Chi tiết",
    )
    do_readonly = fields.Boolean("Readonly?", compute="set_readonly_fields")

    # =================================
    # ORM/CRUD Methods
    # =================================

    def _validate_policy_done_not_unlink(self):
        for policy in self:
            if policy.state == "done":
                raise UserError(
                    f"Phần tính toán chiết khấu cho tháng {policy.month}/{policy.year} đã được Duyệt. Không thể xoá! "
                )

    @api.constrains("discount_product_warranty_policy_id", "month", "year")
    def _validate_discount_policy_already_exist(self):
        for policy in self:
            if (
                policy.discount_product_warranty_policy_id
                and policy.month
                and policy.year
            ):
                policy_exist = self.env[
                    "mv.compute.discount.product.warranty.policy"
                ].search_count(
                    [
                        ("id", "!=", policy.id),
                        (
                            "discount_product_warranty_policy_id",
                            "=",
                            policy.discount_product_warranty_policy_id.id,
                        ),
                        ("month", "=", policy.month),
                        ("year", "=", policy.year),
                    ]
                )
                if policy_exist > 0:
                    raise ValidationError(
                        f"Chính sách của {policy.month}/{policy.year} đã được tạo hoặc đã được tính toán rồi!"
                    )

    @api.constrains("report_date", "discount_product_warranty_policy_id")
    def _validate_time_frame_of_discount_policy(self):
        for policy_compute in self:
            if (
                policy_compute.discount_product_warranty_policy_id
                and policy_compute.report_date
            ):
                policy = policy_compute.discount_product_warranty_policy_id
                if (
                    not policy.date_from
                    <= policy_compute.report_date.date()
                    <= policy.date_to
                ):
                    raise ValidationError(
                        "Tháng cần tính toán phải nằm trong khoảng thời gian quy định của chính sách!"
                    )

    @api.constrains("year", "month")
    def _check_month_year_not_overlap(self):
        for rec in self:
            if self.search_count(
                [
                    ("year", "=", rec.year),
                    ("month", "=", rec.month),
                    ("id", "!=", rec.id),
                ]
            ):
                raise UserError("Bản ghi với tên %s đã tồn tại!" % rec.name)

    @api.depends("year", "month")
    def _compute_name_from_date_parts(self):
        """
        Compute the name based on the month and year.
        Sets the `name` field to "month/year" if both `month` and `year` are set.
        If either is not set, it uses the current month and year.
        """
        for rec in self:
            if rec.month and rec.year:
                date_str = "{}/{}".format(str(rec.month), str(rec.year))
            else:
                date_str = get_current_date_string()
            rec.name = date_str

    @api.depends("year", "month")
    def _compute_report_date(self):
        """
        Compute the `report_date` based on the month and year.

        This method sets the `report_date` field to the first day of the given month and year
        if both `month` and `year` are set. If either is not set, it uses the first day of the current month and year.

        :return: None
        """
        for rec in self:
            try:
                month = int(rec.month) if rec.month else datetime.now().month
                year = int(rec.year) if rec.year else datetime.now().year
                rec.report_date = datetime.now().replace(day=1, month=month, year=year)
            except ValueError:
                rec.report_date = datetime.now().replace(day=1)

    def unlink(self):
        """Override the unlink method to prevent deletion of confirmed records."""
        self._validate_policy_done_not_unlink()
        self.env["mv.compute.discount.product.warranty.policy.line"].search(
            [("parent_id", "in", self.ids)]
        ).unlink()

        return super(MvComputeDiscountProductWarrantyPolicy, self).unlink()

    # =================================
    # BUSINESS Methods
    # =================================

    def action_confirm(self):
        """
        Confirm the record and calculate the discount lines.
        - Fetch all tickets that have products.
        - Fetch all product moves related to the tickets.
        - Get partners who are eligible for discounts.
        - Process partners to compute discount information.
        - Confirm the record and update the line_ids.
        :return: None
        """
        self.ensure_one()

        if not self.discount_product_warranty_policy_id:
            raise ValidationError("Chưa chọn Chính sách chiết khấu!")

        policy_used = self.discount_product_warranty_policy_id
        policy_product_apply_ids = policy_used.product_apply_reward_ids

        date_from, date_to = self.calculate_start_and_end_dates(
            self.report_date,
            self.month,
            self.year,
        )
        self.line_ids = False
        self._invalidate_lines()

        tickets = self._fetch_tickets([date_from, date_to], [])
        if not tickets:
            self._raise_no_tickets_error(self.month, self.year, no_tickets=True)

        ticket_product_moves = self._fetch_ticket_product_moves(tickets)
        if policy_product_apply_ids:
            if not ticket_product_moves:
                raise ValidationError(
                    "Không tìm thấy sản phẩm theo chính sách kích hoạt trong tháng {}/{}".format(
                        self.month, self.year
                    )
                )
            ticket_product_moves = ticket_product_moves.filtered(
                lambda t: t.product_id.product_tmpl_id.id
                in policy_product_apply_ids.mapped("product_template_id").ids
            )

        partners = self._get_discount_eligible_partners(ticket_product_moves)

        calc_line_ids = self._process_disc_for_partners(partners, ticket_product_moves)
        if not calc_line_ids:
            self._raise_no_tickets_error(self.month, self.year, no_tickets=False)

        self.write({"line_ids": calc_line_ids, "state": "confirm"})

    def calculate_start_and_end_dates(self, report_date, target_month, target_year):
        """
        Computes the start and end dates of a given month and year.

        :param target_year:  The target year.
        :param target_month:  The target month.
        :param report_date:  The report date.
        :return:  A tuple containing the start and end dates of the given month and year.
        """

        DAY_START = 1
        HOUR_START = 0
        MINUTE_START = 0
        SECOND_START = 0
        MICROSECOND_START = 0

        try:
            date_from = report_date.replace(
                day=DAY_START,
                month=int(target_month),
                year=int(target_year),
                hour=HOUR_START,
                minute=MINUTE_START,
                second=SECOND_START,
                microsecond=MICROSECOND_START,
            )
            date_to = date_from + relativedelta(months=1)
            return date_from, date_to
        except Exception as e:
            _logger.error("Failed to compute dates: %s", e)
            return None, None

    def _invalidate_lines(self):
        """Invalidate current line_ids."""
        self.write({"line_ids": False})

    def _raise_no_tickets_error(self, month, year, no_tickets=False):
        """Raise an error if no tickets are found or no data for the given month."""
        if no_tickets:
            error_message = (
                f"Không có phiếu nào đã kích hoạt trong tháng {month}/{year}"
            )
        else:
            error_message = f"Không có dữ liệu trong tháng {month}/{year}"

        raise UserError(error_message)

    def _fetch_tickets(self, date_range, additional_domain=[]):
        """Fetch tickets based on the given date range and additional domain."""
        try:
            # Cache the stage references to avoid multiple lookups
            # Only the "New" and "Done" stages are relevant for Warranty Activation
            stage_new_id = self.env.ref("mv_website_helpdesk.warranty_stage_new").id
            stage_done_id = self.env.ref("mv_website_helpdesk.warranty_stage_done").id

            base_domain = [
                ("helpdesk_ticket_product_move_ids", "!=", False),
                ("ticket_type_id.code", "in", [SUB_DEALER_CODE, END_USER_CODE]),
            ]
            if stage_new_id and stage_done_id:
                base_domain += [("stage_id", "in", [stage_new_id, stage_done_id])]

            if date_range:
                base_domain += [
                    ("create_date", ">=", date_range[0]),
                    ("create_date", "<", date_range[1]),
                ]

            return self.env["helpdesk.ticket"].search(base_domain + additional_domain)

        except ValueError as ve:
            _logger.error(f"Value error in fetching tickets: {ve}")
        except self.env["helpdesk.ticket"]._exceptions.AccessError as ae:
            _logger.error(f"Access error in fetching tickets: {ae}")
        except Exception as e:
            _logger.error(f"Unexpected error in fetching tickets: {e}")

        return self.env["helpdesk.ticket"]

    def _fetch_ticket_product_moves(self, tickets):
        """Fetch product moves related to given tickets."""

        if not tickets:
            return self.env[TICKET_PRODUCT_MOVE_MODEL]

        base_domain = [
            ("helpdesk_ticket_id", "in", tickets.ids),
            ("helpdesk_ticket_type_id.code", "in", [SUB_DEALER_CODE, END_USER_CODE]),
            ("product_activate_twice", "=", False),
        ]

        try:
            ticket_product_moves = self.env[TICKET_PRODUCT_MOVE_MODEL].search(
                base_domain
            )
            return ticket_product_moves
        except Exception as e:
            _logger.error(f"Failed to fetch ticket product moves: {e}", exc_info=True)
            return self.env[TICKET_PRODUCT_MOVE_MODEL]

    def _get_discount_eligible_partners(self, ticket_product_moves):
        """Get partners who are eligible for discounts based on the given order lines."""
        try:
            partners = self._fetch_discount_partners(self.month, self.year)
            return ticket_product_moves.mapped("partner_id").filtered(
                lambda line: (
                    line.id in self.env["res.partner"].sudo().browse(partners.ids).ids
                    if partners
                    else []
                )
            )
        except Exception as error:
            _logger.error("Error in fetching discount eligible partners: %s", error)
            return self.env["res.partner"]

    def _fetch_discount_partners(self, month, year):
        """
        Fetches the partners who are eligible for discounts in a given month and year.

        Args:
            month (str): The target month.
            year (str): The target year.

        Returns:
            recordset: A recordset of partners who are eligible for discounts.
        """
        try:
            self.env["mv.discount.partner"].flush_model()
            query = self._build_discount_partners_query()
            self.env.cr.execute(query, [year, month])

            partner_ids = [result[1] for result in self.env.cr.fetchall()]
            return (
                self.env["res.partner"]
                .browse(partner_ids)
                .filtered(lambda p: p.use_for_report)
            )
        except Exception as error:
            _logger.error("Failed to fetch partners for discount: %s", error)
            return self.env["res.partner"]

    def _build_discount_partners_query(self):
        """
        Builds the SQL query to fetch discount eligible partners.

        Returns:
            str: The SQL query string.
        """
        return """
            WITH date_params AS (SELECT %s::INT AS target_year, %s::INT AS target_month)
            SELECT dp.parent_id AS mv_discount_id, dp.partner_id, dp.level
            FROM mv_discount_partner dp
                JOIN date_params AS d ON (EXTRACT(YEAR FROM dp.date) = d.target_year)
            GROUP BY 1, dp.partner_id, dp.level
            ORDER BY dp.partner_id, dp.level;
        """

    def _process_disc_for_partners(self, partners, ticket_product_moves):
        """Process partners to compute discount information."""

        list_line_ids = []
        tickets = ticket_product_moves
        policy = self.discount_product_warranty_policy_id
        compute_date = self.report_date

        for partner in partners:
            vals = self._prepare_values_for_confirmation(partner, compute_date)
            tickets_registered = self._get_tickets_by_partner(tickets, partner)
            tickets_registered_child = self._get_tickets_by_child(tickets, partner)

            tickets_registered += tickets_registered_child
            vals["ticket_product_moves_ids"] += tickets_registered.ids
            vals["product_activation_count"] = len(list(set(tickets_registered)))

            total_reward_amount = self._compute_total_reward_amount(
                policy=policy, tickets=tickets_registered, vals=vals
            )
            vals["total_reward_amount"] = total_reward_amount

            list_line_ids.append((0, 0, vals))

        return list_line_ids

    def _prepare_values_for_confirmation(self, partner, compute_date):
        """Prepare values for confirmation of the given partner and report date."""
        self.ensure_one()

        return {
            "parent_id": self.id,
            "compute_date": compute_date,
            "partner_id": partner.id,
            "currency_id": partner.company_id.sudo().currency_id
            or self.env.company.currency_id.id,
            "ticket_product_moves_ids": [],
            "product_activation_count": 0,
        }

    def _get_tickets_by_partner(self, tickets, partner):
        """Get tickets by partner."""
        return tickets.filtered(lambda ticket: ticket.partner_id.id == partner.id)

    def _get_tickets_by_child(self, tickets, partner):
        """Get tickets by partner's children."""
        childs_of_partner = self.env["res.partner"].search(
            [("is_agency", "=", False), ("parent_id", "=", partner.id)]
        )
        return tickets.search([("partner_id", "in", childs_of_partner.ids)])

    def _compute_total_reward_amount(self, policy, tickets, vals):
        products = tickets.mapped("product_id")
        total_reward_amount = 0

        for p in policy.product_apply_reward_ids:
            for product in products:
                if product.id == p.product_id.id:
                    total_reward_amount += (
                        p.reward_amount * vals["product_activation_count"]
                    )

        return total_reward_amount

    def action_approve(self):
        """Approve the record and update the partner amounts."""
        if not self._has_approval_access(self.env):
            raise AccessError("Bạn không có quyền duyệt!")

        for record in self.filtered(lambda r: len(r.line_ids) > 0):
            partners_updates = self._calculate_partners_updates(record)
            self._update_partner_amounts(partners_updates)

            record.write({"state": "done", "approved_date": fields.Datetime.now()})

    def _calculate_partners_updates(self, record):
        updates = {}
        for compute_line in record.line_ids:
            partner_id = compute_line.partner_id.id
            total_money = compute_line.total_reward_amount
            updates[partner_id] = updates.get(partner_id, 0) + total_money
        return updates

    def _update_partner_amounts(self, partners_updates):
        for partner_id, total_money in partners_updates.items():
            partner = self.env["res.partner"].sudo().browse(partner_id)
            partner.write({"amount": partner.amount + total_money})

    def action_cancel(self):
        """Cancel the record and delete all lines."""
        for record in self:
            record.line_ids.unlink()
            record.write({"state": "draft", "approved_date": False})


class MvComputeDiscountProductWarrantyPolicyLine(models.Model):
    _name = _description = "mv.compute.discount.product.warranty.policy.line"

    parent_id = fields.Many2one(
        "mv.compute.discount.product.warranty.policy",
        domain=[("active", "=", True)],
        readonly=True,
    )
    compute_date = fields.Datetime(readonly=True)
    name = fields.Char(compute="_compute_parent_name", store=True)
    state = fields.Selection(related="parent_id.state", store=True, readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    partner_id = fields.Many2one("res.partner", "Đại lý", readonly=True)
    partner_company_ref = fields.Char(
        related="partner_id.company_registry",
        string="Mã đại lý",
        store=True,
    )
    ticket_product_moves_ids = fields.Many2many(
        "mv.helpdesk.ticket.product.moves",
        "compute_disc_product_warranty_policy_ticket_product_rel",
        "compute_disc_product_warranty_policy_id",
        "helpdesk_ticket_product_moves_id",
        "Danh sách sản phẩm kích hoạt",
        readonly=True,
    )
    product_activation_count = fields.Integer(readonly=True, default=0)
    total_reward_amount = fields.Monetary(readonly=True, currency_field="currency_id")

    @api.depends("compute_date")
    def _compute_parent_name(self):
        for line in self:
            if line.compute_date:
                line.name = "{}/{}".format(
                    str(line.compute_date.month),
                    str(line.compute_date.year),
                )
            else:
                dt = datetime.now().replace(day=1)
                line.name = "{}/{}".format(str(dt.month), str(dt.year))

    @api.autovacuum
    def _gc_compute_discount_policy_line(self):
        """Delete all lines that are not linked to the parent."""
        lines_to_del = self.env[self._name].search([("parent_id", "=", False)])
        if lines_to_del:
            lines_to_del.unlink()
            _logger.info("Successfully deleted unlinked policy lines.")
        else:
            _logger.info("No unlinked policy lines found.")
