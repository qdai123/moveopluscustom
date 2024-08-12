# -*- coding: utf-8 -*-
import base64
import calendar
import io
import logging
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError
from odoo.tools.misc import formatLang

_logger = logging.getLogger(__name__)

DEFAULT_SERVER_DATE_FORMAT = "%Y-%m-%d"
DEFAULT_SERVER_TIME_FORMAT = "%H:%M:%S"
DEFAULT_SERVER_DATETIME_FORMAT = "%s %s" % (
    DEFAULT_SERVER_DATE_FORMAT,
    DEFAULT_SERVER_TIME_FORMAT,
)

# Constants
DECEMBER = "12"
QUARTER_OF_YEAR = ["3", "6", "9", "12"]


def get_years():
    year_list = []
    for year in range(2000, 2100):
        year_list.append((str(year), str(year)))
    return year_list


def get_months():
    return [
        ("1", "1"),
        ("2", "2"),
        ("3", "3"),
        ("4", "4"),
        ("5", "5"),
        ("6", "6"),
        ("7", "7"),
        ("8", "8"),
        ("9", "9"),
        ("10", "10"),
        ("11", "11"),
        ("12", "12"),
    ]


class MvComputeDiscount(models.Model):
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _name = "mv.compute.discount"
    _description = _("Compute Discount (%) for Partner")

    @api.model
    def default_get(self, fields_list):
        res = super(MvComputeDiscount, self).default_get(fields_list)
        promote_discount = (
            self.env["mv.discount"]
            .search([("level_promote_apply", "!=", False)], limit=1)
            .level_promote_apply
        )
        if promote_discount:
            res["level_promote_apply_for"] = promote_discount
        return res

    def _default_level(self):
        return (
            self.env["mv.discount"]
            .search([("level_promote_apply", "!=", False)], limit=1)
            .level_promote_apply
        )

    def _get_promote_discount_level(self):
        for record in self:
            record.level_promote_apply_for = self._default_level()

    @api.depends("month", "year")
    def _compute_name(self):
        for record in self:
            record.name = "{}/{}".format(str(record.month), str(record.year))

    def _do_readonly(self):
        for rec in self:
            if rec.state in ["done"]:
                rec.do_readonly = True
            else:
                rec.do_readonly = False

    # RULE Fields:
    do_readonly = fields.Boolean("Readonly?", compute="_do_readonly")

    # BASE Fields:
    name = fields.Char(compute="_compute_name", default="New", store=True)
    year = fields.Selection(get_years(), "Năm")
    month = fields.Selection(get_months(), "Tháng")
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("confirm", "Lưu"),
            ("done", "Đã Duyệt"),
        ],
        "Trạng thái",
        default="draft",
        tracking=True,
        readonly=True,
    )
    line_ids = fields.One2many("mv.compute.discount.line", "parent_id")
    report_date = fields.Datetime(
        compute="_compute_report_date_by_month_year", store=True
    )
    level_promote_apply_for = fields.Integer(
        "Bậc áp dụng (Khuyến khích)", compute="_get_promote_discount_level"
    )

    _sql_constraints = [
        (
            "month_year_uniq",
            "unique (month, year)",
            "Tháng và năm này đã tồn tại không được tạo nữa!",
        )
    ]

    @api.depends("year", "month")
    def _compute_report_date_by_month_year(self):
        for rec in self:
            if rec.month and rec.year:
                rec.report_date = datetime.now().replace(
                    day=1, month=int(rec.month), year=int(rec.year)
                )
            else:
                rec.report_date = rec.create_date.replace(
                    day=1,
                    month=int(rec.create_date.month),
                    year=int(rec.create_date.year),
                )

    # =================================
    # BUSINESS Methods
    # =================================

    def action_reset_to_draft(self):
        try:
            self.ensure_one()
            if self.state != "draft":
                self.state = "draft"
        except Exception as e:
            _logger.error("Failed to reset to draft: %s", e)
            pass

    def action_confirm(self):
        """
        Confirms the computation of discounts for partners. It performs several operations including filtering and searching for records,
        and updating the state of the record.

        Returns:
            None
        """
        self.ensure_one()

        date_from, date_to = self._get_dates(self.report_date, self.month, self.year)
        self.line_ids = False
        list_line_ids = []

        # Fetch all sale orders at once
        sale_orders = self.env["sale.order"].search(
            [
                ("is_order_returns", "=", False),
                ("state", "=", "sale"),
                ("date_invoice", ">=", date_from),
                ("date_invoice", "<", date_to),
            ]
        )

        if not sale_orders:
            raise UserError(
                "Hiện tại không có đơn hàng nào đã thanh toán trong tháng %s"
                % self.month
            )

        # Filter order lines at once with the following conditions:
        # - Partner is an agency
        # - Product category is eligible for discount
        # - Product type is 'product'
        # - Quantity delivered is greater than 0
        # - Quantity invoiced is greater than 0
        order_lines = sale_orders.order_line.filtered(
            lambda order: order.order_id.partner_id.is_agency
            and order.order_id.check_category_product(order.product_id.categ_id)
            and order.product_id.detailed_type == "product"
            and order.qty_delivered > 0
            and order.qty_invoiced > 0
        )

        # Fetch partners at once
        partners_use_for_discount = self._get_partner_for_discount_only(
            self.month, self.year
        )
        partners = order_lines.order_id.mapped("partner_id").filtered(
            lambda rec: (
                rec.id
                in self.env["res.partner"]
                .sudo()
                .browse(partners_use_for_discount.ids)
                .ids
                if partners_use_for_discount
                else []
            )
        )

        for partner_id in partners:
            total_quantity_minimum = 0
            total_quantity_maximum = 0
            total_quantity_delivered = 0
            total_quantity_for_discount = 0
            total_sales = 0

            vals = self._prepare_values_for_confirmation(partner_id, self.report_date)
            partner = self.env["res.partner"].sudo().browse(partner_id.id)

            # [GET] All Orders of Partner
            order_by_partner_agency = order_lines.filtered(
                lambda sol: sol.order_id.partner_id == partner
            )
            vals["currency_id"] = order_by_partner_agency[0].order_id.currency_id.id

            # [GET] All Orders of Partner has (parent_id = partner_id)
            childs_of_partner = self.env["res.partner"].search(
                [("parent_id", "=", partner.id)]
            )
            orders_by_child_of_partner_agency = sale_orders.search(
                [("partner_id", "in", childs_of_partner.ids)]
            ).order_line.filtered(
                lambda sol: sol.order_id.check_category_product(sol.product_id.categ_id)
                and sol.product_id.detailed_type == "product"
                and sol.qty_delivered > 0
            )
            if orders_by_child_of_partner_agency:
                order_by_partner_agency += orders_by_child_of_partner_agency

            # [UP] Update Quantity (Get only with [qty_delivered] field)
            total_quantity_delivered += sum(
                order_by_partner_agency.filtered(lambda rec: rec.price_unit > 0).mapped(
                    "qty_delivered"
                )
            )
            vals["quantity"] = total_quantity_delivered

            # [UP] Update Quantity Discount (Get only with [qty_delivered] field)
            total_quantity_for_discount += sum(
                order_by_partner_agency.filtered(
                    lambda rec: rec.price_unit == 0
                ).mapped("qty_delivered")
            )
            vals["quantity_discount"] = total_quantity_for_discount

            # [!] Determine Partner Discount Level
            line_ids = partner.line_ids.filtered(
                lambda discount: (
                    date.today() >= discount.date
                    if discount.date
                    else not discount.date
                )
            ).sorted("level")

            if line_ids:
                compute_discount_line = self.env["mv.compute.discount.line"]

                # [UP] Update Total Sales
                total_sales += sum(
                    order_by_partner_agency.filtered(
                        lambda rec: rec.price_unit > 0
                    ).mapped("price_subtotal_before_discount")
                )
                vals["amount_total"] = total_sales

                level = line_ids[-1].level
                discount_id = line_ids[-1].parent_id
                discount_line_id = discount_id.line_ids.filtered(
                    lambda rec: rec.level == level
                )
                vals["level"] = discount_line_id.level
                total_quantity_minimum += discount_line_id.quantity_from
                vals["quantity_from"] = total_quantity_minimum
                total_quantity_maximum += discount_line_id.quantity_to
                vals["quantity_to"] = total_quantity_maximum

                quantity_required_to_discount = (
                    total_quantity_delivered >= total_quantity_minimum
                )
                if quantity_required_to_discount:
                    # [>] Để đạt được chỉ tiêu 1 tháng => Chỉ cần thỏa số lượng trong tháng
                    discount_for_a_month = discount_line_id.month
                    vals["is_month"] = True
                    vals["month"] = discount_for_a_month
                    vals["month_money"] = total_sales * discount_for_a_month / 100

                    # [>] Để đạt kết quả 2 tháng:
                    # 1 - tháng này phải đạt chỉ tiêu tháng
                    # 2 - tháng trước phải đạt chỉ tiêu tháng và chưa đạt chỉ tiêu 2 tháng
                    if self.month == "1":
                        name = "12" + "/" + str(int(self.year) - 1)
                    else:
                        name = str(int(self.month) - 1) + "/" + self.year

                    line_two_month_id = compute_discount_line.search(
                        [
                            ("partner_id", "=", partner.id),
                            ("name", "=", name),
                            ("is_month", "=", True),
                            ("is_two_month", "=", False),
                        ]
                    )
                    if line_two_month_id:
                        discount_for_two_month = discount_line_id.two_month
                        vals["is_two_month"] = True
                        vals["two_month"] = discount_for_two_month
                        vals["amount_two_month"] = (
                            line_two_month_id.amount_total + total_sales
                        )
                        vals["two_money"] = (
                            (line_two_month_id.amount_total + total_sales)
                            * discount_for_two_month
                            / 100
                        )

                    # [>] Để đạt kết quả quý [1, 2, 3] [4, 5, 6] [7, 8, 9] [10, 11, 12]:
                    # [>] Chỉ xét quý vào các tháng 3 6 9 12, chỉ cần kiểm tra 2 tháng trước đó có đạt chỉ tiêu tháng ko
                    if self.month in QUARTER_OF_YEAR:
                        name_one = str(int(self.month) - 1) + "/" + self.year
                        name_two = str(int(self.month) - 2) + "/" + self.year
                        line_name_one = compute_discount_line.search(
                            [
                                ("partner_id", "=", partner.id),
                                ("name", "=", name_one),
                                ("is_month", "=", True),
                            ]
                        )
                        line_name_two = compute_discount_line.search(
                            [
                                ("partner_id", "=", partner.id),
                                ("name", "=", name_two),
                                ("is_month", "=", True),
                            ]
                        )
                        if line_name_one and line_name_two:
                            discount_for_quarter = discount_line_id.quarter
                            vals["is_quarter"] = True
                            vals["quarter"] = discount_for_quarter
                            vals["quarter_money"] = (
                                (
                                    total_sales
                                    + line_name_one.amount_total
                                    + line_name_two.amount_total
                                )
                                * discount_for_quarter
                                / 100
                            )

                    # [>] Để đạt kết quả năm thì tháng đang xét phải là 12
                    # [>] Kiểm tra 11 tháng trước đó đã được chỉ tiêu tháng chưa
                    if self.month == DECEMBER:
                        flag = True
                        total_year = 0
                        for i in range(12):
                            name = str(i + 1) + "/" + self.year
                            line_name = compute_discount_line.search(
                                [
                                    ("partner_id", "=", partner.id),
                                    ("name", "=", name),
                                    ("is_month", "=", True),
                                ]
                            )
                            if not line_name:
                                flag = False
                            total_year += line_name.amount_total

                        if flag:
                            discount_for_year = discount_line_id.quarter
                            vals["is_year"] = True
                            vals["year"] = discount_for_year
                            vals["year_money"] = total_year * discount_for_year / 100

                if discount_line_id and discount_line_id.level >= 0:
                    sale_ids = order_by_partner_agency.order_id.ids
                    order_line_ids = order_by_partner_agency.ids

                    if orders_by_child_of_partner_agency:
                        sale_ids += orders_by_child_of_partner_agency.mapped(
                            "order_id"
                        ).ids
                        order_line_ids += orders_by_child_of_partner_agency.ids

                    vals["sale_ids"] = sale_ids
                    vals["order_line_ids"] = order_line_ids
                    vals["discount_line_id"] = discount_line_id.id

                list_line_ids.append((0, 0, vals))

        if not list_line_ids:
            raise UserError(
                _("Không có dữ liệu để tính chiết khấu cho tháng %s") % self.month
            )

        self.write({"line_ids": list_line_ids, "state": "confirm"})

        # Create history line for discount
        if self.line_ids:
            for line in self.line_ids.filtered(lambda rec: rec.parent_id):
                self.create_history_line(
                    line,
                    "confirm",
                    "Chiết khấu sản lượng tháng %s đang chờ duyệt." % line.name,
                )

    def action_done(self):
        if not self._access_approve():
            raise AccessError("Bạn không có quyền duyệt!")

        for record in self.filtered(lambda r: len(r.line_ids) > 0):
            partners_updates = {}
            for discount_line in record.line_ids:
                partner_id = discount_line.partner_id.id
                total_money = discount_line.total_money
                partners_updates[partner_id] = (
                    partners_updates.get(partner_id, 0) + total_money
                )

            for partner_id, total_money in partners_updates.items():
                partner = self.env["res.partner"].sudo().browse(partner_id)
                partner.write({"amount": partner.amount + total_money})

            # Create history line for discount
            for line in record.line_ids.filtered(lambda rec: rec.parent_id):
                record.create_history_line(
                    line,
                    "done",
                    "Chiết khấu sản lượng tháng %s đã được duyệt." % line.name,
                )

            # Create total discount detail history
            record.create_total_discount_detail_history()
            record.write({"state": "done"})

    def action_undo(self):
        # Create history line for discount
        for record in self:
            if record.line_ids:
                for line in record.line_ids.filtered(lambda rec: rec.parent_id):
                    self.create_history_line(
                        line,
                        "cancel",
                        "Chiết khấu sản lượng tháng %s đã bị từ chối và đang chờ xem xét."
                        % line.name,
                    )

            record.write({"state": "draft", "line_ids": False})

    def create_history_line(self, record, state, description):
        total_money = record.total_money
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
            production_discount_policy_id=record.id,
            production_discount_policy_total_money=total_money,
            total_money=total_money,
            total_money_discount_display=money_display,
            is_waiting_approval=is_waiting_approval,
            is_positive_money=is_positive_money,
            is_negative_money=is_negative_money,
        )

    def create_total_discount_detail_history(self):
        for line in self.line_ids.filtered(lambda rec: rec.parent_id):
            self.env[
                "mv.partner.total.discount.detail.history"
            ]._create_total_discount_detail_history_line(parent_id=self, policy_id=line)

    def _prepare_values_for_confirmation(self, partner_id, report_date):
        """Gets the data and returns it the right format for render."""
        self.ensure_one()

        return {
            "month_parent": int(report_date.month),
            "partner_id": partner_id.id,
            "discount_line_id": False,
            "currency_id": False,
            "level": 0,
            "sale_ids": [],
            "order_line_ids": [],
            "quantity": 0,
            "quantity_discount": 0,
            "quantity_from": 0,
            "quantity_to": 0,
            "amount_total": 0,
            # Compute for a month
            "is_month": False,
            "month": 0.0,  # % chiết khấu tháng
            "month_money": 0.0,
            # Compute for 2 months
            "is_two_month": False,
            "amount_two_month": 0.0,
            "two_month": 0.0,  # % chiết khấu 2 tháng
            "two_money": 0,
            # Compute for quarter
            "is_quarter": False,
            "quarter": 0.0,  # % chiết khấu quý
            "quarter_money": 0,
            # Compute for year
            "is_year": False,
            "year": 0.0,  # % chiết khấu năm
            "year_money": 0,
        }

    # =================================
    # ACTION Methods
    # =================================

    def action_view_tree(self):
        return {
            "type": "ir.actions.act_window",
            "name": "Kết quả chiết khấu của tháng: %s" % self.name,
            "res_model": "mv.compute.discount.line",
            "view_mode": "tree,form",
            "views": [
                [
                    self.env.ref("mv_sale.mv_compute_discount_line_tree").id,
                    "tree",
                ],
                [
                    self.env.ref("mv_sale.mv_compute_discount_line_form").id,
                    "form",
                ],
            ],
            "search_view_id": [
                self.env.ref("mv_sale.mv_compute_discount_line_search_view").id,
                "search",
            ],
            "domain": [("parent_id", "=", self.id)],
            "context": {
                "create": False,
                "edit": False,
                "tree_view_ref": "mv_sale.mv_compute_discount_line_tree",
                "form_view_ref": "mv_sale.mv_compute_discount_line_form",
                "search_default_filter_partner_sales_state": True,
            },
        }

    # =================================
    # HELPER / PRIVATE Methods
    # =================================

    # TODO: Implement this method to reload discount lines - Phat Dang <phat.dangminh@moveoplus.com>
    def action_reload_discount_line(self):
        try:
            _logger.info("Starting to reload discount lines.")
            compute_discount_line = self.env["mv.compute.discount.line"]
            parent_discount = self.filtered(lambda rec: rec.line_ids)
            for line in parent_discount.line_ids:
                total_sales = 0

                if line.is_two_month:
                    if line.month_parent == "1":
                        first_month_of_two = "12/" + str(int(line.parent_id.year) - 1)
                        second_month_of_two = "12/" + str(int(line.parent_id.year) - 1)
                    else:
                        first_month_of_two = (
                            str(int(line.month_parent) - 1) + "/" + line.parent_id.year
                        )
                        second_month_of_two = (
                            str(int(line.month_parent) - 1) + "/" + line.parent_id.year
                        )
                    line_ids = compute_discount_line.search(
                        [
                            (
                                "name",
                                "in",
                                [first_month_of_two, second_month_of_two],
                            ),
                            ("partner_id", "=", line.partner_id.id),
                        ]
                    )
                    total_sales += (
                        sum(line_ids.mapped("amount_total")) + line.amount_total
                    )

                # [>] Tính toán lại Tiền Chiết Khấu Quý
                if line.is_quarter:
                    first_month_of_quarter = (
                        str(int(line.month_parent) - 1) + "/" + line.parent_id.year
                    )
                    second_month_of_quarter = (
                        str(int(line.month_parent) - 1) + "/" + line.parent_id.year
                    )
                    line_ids = compute_discount_line.search(
                        [
                            (
                                "name",
                                "in",
                                [first_month_of_quarter, second_month_of_quarter],
                            ),
                            ("partner_id", "=", line.partner_id.id),
                        ]
                    )
                    total_sales += (
                        sum(line_ids.mapped("amount_total")) + line.amount_total
                    )

                # [>] Tính toán lại Tiền Chiết Khấu Năm (Tính cả năm)
                if line.is_year:
                    for month in range(12):
                        month_used = str(month + 1) + "/" + line.parent_id.year
                        line_name = compute_discount_line.search(
                            [
                                ("name", "=", month_used),
                                ("partner_id", "=", line.partner_id.id),
                            ]
                        )
                        total_sales += line_name.amount_total

                self._calculate_discounts_for_line(total_sales, line)
            _logger.info("Successfully reloaded discount lines.")
        except Exception as e:
            _logger.error("Error reloading discount lines: %s", e)

    def _calculate_discounts_for_line(self, total_sales, line):
        discount_types = [
            (
                "is_promote_discount",
                "promote_discount_percentage",
                "promote_discount_money",
            ),
            ("is_month", "month", "month_money"),
            ("is_two_month", "two_month", "two_money"),
            ("is_quarter", "quarter", "quarter_money"),
            ("is_year", "year", "year_money"),
        ]
        for (
            is_discount_type,
            discount_percentage_field,
            discount_money_field,
        ) in discount_types:
            if getattr(line, is_discount_type):
                percentage = getattr(line, discount_percentage_field) / 100
                setattr(line, discount_money_field, total_sales * percentage)
        line._compute_total_money()

    # TODO: End of implementation - Phat Dang

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

    def _get_partner_for_discount_only(self, month, year):
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
            query = """
                WITH date_params AS (SELECT %s::INT AS target_year, %s::INT AS target_month)
                SELECT dp.parent_id AS mv_discount_id, dp.partner_id, dp.level
                FROM mv_discount_partner dp
                    JOIN date_params AS d ON (EXTRACT(YEAR FROM dp.date) = d.target_year)
                GROUP BY 1, dp.partner_id, dp.level
                ORDER BY dp.partner_id, dp.level;
            """
            self.env.cr.execute(query, [year, month])
            partner_ids = [r[1] for r in self.env.cr.fetchall()]
            return self.env["res.partner"].browse(partner_ids)
        except Exception as e:
            _logger.error("Failed to fetch partners for discount: %s", e)
            return self.env["res.partner"]

    def _access_approve(self):
        """
            Helps check user security for access to Discount/Discount Line approval
        :return: True/False
        """
        return self.env.user.has_group("mv_sale.group_mv_compute_discount_approver")

    # ===================
    # REPORT Action/Data
    # ===================

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

    def get_days_in_month(self):
        try:
            year = int(self[0].report_date.year)
            month = int(self[0].report_date.month)
            return [
                day
                for week in calendar.monthcalendar(year, month)
                for day in week
                if day != 0  # Filter out days that belong to other months (value 0)
            ]
        except ValueError:
            return []

    def get_weekdays_in_month(self):
        try:
            year = int(self[0].report_date.year)
            month = int(self[0].report_date.month)
            weekdays = [
                "Mon",
                "Tue",
                "Wed",
                "Thu",
                "Fri",
                "Sat",
                "Sun",
            ]
            dates = []

            for week in calendar.monthcalendar(year, month):
                for day in week:
                    if day != 0:
                        d = f"{year}-{month:02d}-{day:02d}"
                        day_of_week = weekdays[calendar.weekday(year, month, day)]
                        dates.append((d, day_of_week))

            return [weekday[1] for weekday in dates]
        except ValueError:
            return []

    def _get_compute_discount_detail_data(self, report_date, pass_security=False):
        report_lines = []
        self.env["mv.compute.discount.line"].flush_model()
        query = """
            SELECT ROW_NUMBER() OVER ()                    AS row_index,
                       partner.name                            AS sub_dealer,
                       cdl.level                               AS level,
                       cdl.quantity_from                       AS quantity_from,
                       cdl.quantity                            AS quantity,
                       cdl.quantity_discount                   AS quantity_discount,
                       cdl.amount_total                        AS total,
                       cdl.month_money                         AS month_money,
                       cdl.two_money                           AS two_money,
                       cdl.quarter_money                       AS quarter_money,
                       cdl.year_money                          AS year_money,
                       COALESCE(cdl.promote_discount_money, 0) AS promote_discount_money,
                       cdl.total_money                         AS total_money
            FROM mv_compute_discount_line cdl
                JOIN res_partner partner ON partner.id = cdl.partner_id
            WHERE cdl.parent_id = %s;
        """
        self.env.cr.execute(query, [self.id])
        for data in self.env.cr.dictfetchall():
            report_lines.append(
                {
                    "index": data["row_index"],
                    "partner_id": data["sub_dealer"],
                    "level": data["level"],
                    "quantity_from": data["quantity_from"],
                    "quantity": data["quantity"],
                    "quantity_discount": data["quantity_discount"],
                    "amount_total": data["total"],
                    "amount_month_money": data["month_money"],
                    "amount_two_money": data["two_money"],
                    "amount_quarter_money": data["quarter_money"],
                    "amount_year_money": data["year_money"],
                    "amount_promote_discount_money": data["promote_discount_money"],
                    "amount_total_money": data["total_money"],
                }
            )
        return report_lines

    def print_report(self):
        months = set(self.mapped("month"))

        if len(months) > 1:
            raise UserError(_("Only export report in ONE MONTH!"))

        # DOWNLOAD Report Data
        file_content, file_name = self.export_to_excel()

        # REMOVE All Excel Files by file_content:
        attachments_to_remove = self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("create_uid", "=", self.env.uid),
                ("create_date", "<", fields.Datetime.now()),
                ("name", "ilike", "Moveoplus-Partners-Discount-Detail%"),
            ]
        )
        if attachments_to_remove:
            attachments_to_remove.unlink()

        # NEW Attachment to download
        new_attachment = (
            self.with_context(ats_penalties_fines=True)
            .env["ir.attachment"]
            .create(
                {
                    "name": file_name,
                    "description": file_name,
                    "datas": base64.b64encode(file_content),
                    "res_model": self._name,
                    "res_id": self.ids[0],
                }
            )
        )

        if len(new_attachment) == 1:
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{new_attachment[0].id}?download=true",
                "target": "self",
            }

        return False

    def export_to_excel(self):
        self.ensure_one()

        if not self:
            raise UserError(_("No data to generate the report for."))

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet()
        file_name = "Moveoplus-Partners-Discount-Detail_%s-%s.xlsx" % (
            self.report_date.month,
            self.report_date.year,
        )
        data_lines = self._get_compute_discount_detail_data(False, False)

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
        DEFAULT_FORMAT = workbook.add_format(base_format)

        # ############# [HEADER] #############
        sheet.set_row(0, 30)

        # ////// NAME = "Chi tiết chiết khấu của Đại Lý trong tháng {month/year}"
        sheet.merge_range("A1:M1", "", DEFAULT_FORMAT)
        format_first_title = [
            "Chi tiết chiết khấu của Đại Lý trong tháng ",
            workbook.add_format(
                {"font_name": "Arial", "font_size": 11, "color": "red", "bold": True}
            ),
            "{}/{}".format(self.month, self.year),
        ]
        sheet.write_rich_string(
            "A1",
            *format_first_title,
            DEFAULT_FORMAT,
        )

        SUB_TITLE_FORMAT = workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "align": "center",
                "valign": "vcenter",
                "border": True,
                "border_color": "black",
                "bold": True,
                "bg_color": "#71C671",
                "text_wrap": True,
            }
        )

        SUB_TITLE_TOTAL_FORMAT = workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "align": "center",
                "valign": "vcenter",
                "border": True,
                "border_color": "black",
                "bold": True,
                "bg_color": "#FFA07A",
                "text_wrap": True,
            }
        )

        # ////// NAME = "Thứ tự"
        sheet.merge_range("A2:A3", "", DEFAULT_FORMAT)
        sheet.write("A2", "#", SUB_TITLE_FORMAT)

        sheet.set_column(1, 0, 3)

        # ////// NAME = "Đại lý"
        sheet.merge_range("B2:B3", "", DEFAULT_FORMAT)
        sheet.write("B2", "Đại lý", SUB_TITLE_FORMAT)

        sheet.set_column(1, 1, 70)

        # ////// NAME = "Cấp bậc"
        sheet.merge_range("C2:C3", "", DEFAULT_FORMAT)
        sheet.write("C2", "Cấp bậc", SUB_TITLE_FORMAT)

        # ////// NAME = "24TA"
        sheet.merge_range("D2:D3", "", DEFAULT_FORMAT)
        sheet.write("D2", "24TA", SUB_TITLE_FORMAT)

        # ////// NAME = "Số lượng lốp đã bán (Cái)"
        sheet.merge_range("E2:E3", "", DEFAULT_FORMAT)
        sheet.write("E2", "SL lốp đã bán (Cái)", SUB_TITLE_FORMAT)

        # ////// NAME = "Số lượng lốp Khuyến Mãi (Cái)"
        sheet.merge_range("F2:F3", "", DEFAULT_FORMAT)
        sheet.write("F2", "SL lốp khuyến mãi (Cái)", SUB_TITLE_FORMAT)

        # ////// NAME = "Doanh thu Tháng"
        sheet.merge_range("G2:G3", "", DEFAULT_FORMAT)
        sheet.write("G2", "Doanh thu", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu tháng"
        sheet.merge_range("H2:H3", "", DEFAULT_FORMAT)
        sheet.write("H2", "Tiền CK Tháng", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu 2 tháng"
        sheet.merge_range("I2:I3", "", DEFAULT_FORMAT)
        sheet.write("I2", "Tiền CK 2 Tháng", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu quý"
        sheet.merge_range("J2:J3", "", DEFAULT_FORMAT)
        sheet.write("J2", "Tiền CK Quý", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu năm"
        sheet.merge_range("K2:K3", "", DEFAULT_FORMAT)
        sheet.write("K2", "Tiền CK Năm", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu khuyến khích"
        sheet.merge_range("L2:L3", "", DEFAULT_FORMAT)
        sheet.write("L2", "Tiền CK Khuyến Khích", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Tổng tiền chiết khấu"
        sheet.merge_range("M2:M3", "", DEFAULT_FORMAT)
        sheet.write("M2", "Tổng tiền", SUB_TITLE_TOTAL_FORMAT)

        sheet.set_column(4, 12, 15)

        # ############# [BODY] #############
        BODY_CHAR_FORMAT = workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "valign": "vcenter",
                "border": True,
                "border_color": "black",
            }
        )
        BODY_NUM_FORMAT = workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "align": "center",
                "valign": "vcenter",
                "border": True,
                "border_color": "black",
            }
        )
        BODY_TOTAL_NUM_FORMAT = workbook.add_format(
            {
                "font_name": "Arial",
                "font_size": 10,
                "align": "right",
                "valign": "vcenter",
                "border": True,
                "border_color": "black",
                "num_format": "#,##0.00",
            }
        )

        column_headers = list(data_lines[0].keys())
        for count, data in enumerate(data_lines, start=3):
            for col, key in enumerate(column_headers):
                if isinstance(data[key], str):
                    sheet.write(count, col, data[key], BODY_CHAR_FORMAT)
                elif isinstance(data[key], int) or isinstance(data[key], float):
                    if col in [6, 7, 8, 9, 10, 11, 12]:
                        sheet.write(count, col, data[key], BODY_TOTAL_NUM_FORMAT)
                    else:
                        sheet.write(count, col, data[key], BODY_NUM_FORMAT)
                else:
                    sheet.write(count, col, data[key])

        # ############# [FOOTER] ###########################################

        workbook.close()
        output.seek(0)

        return output.read(), file_name.replace("-", "_")

    # ==================================
    # TOOLING
    # ==================================

    def get_selection_label(self, model_name, field_name, record_id):
        model = self.env[model_name]
        field = model._fields[field_name]
        selection_values = dict(field.selection)

        record = model.browse(record_id)
        selection_key = getattr(record, field_name)
        selection_label = selection_values.get(selection_key, "Unknown")

        return selection_key, selection_label
