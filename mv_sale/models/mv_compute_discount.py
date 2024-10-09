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
    return [(str(i), str(i)) for i in range(2000, datetime.now().year + 1)]


def get_months():
    return [(str(i), str(i)) for i in range(1, 13)]


def get_current_date_string():
    dt = datetime.now().replace(day=1)
    return "{}/{}".format(str(dt.month), str(dt.year))


GROUP_APPROVER = "mv_sale.group_mv_compute_discount_approver"


class MvComputeDiscount(models.Model):
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _name = "mv.compute.discount"
    _description = _("Compute Discount (%) for Partner")

    _sql_constraints = [
        (
            "month_year_uniq",
            "unique (month, year)",
            "Tháng và năm này đã tồn tại không được tạo nữa!",
        )
    ]

    @staticmethod
    def _has_approval_access(env):
        """
        Check if the user has approval access.

        :param env: Environment context to access user groups.
        :return: True/False
        """
        return env.user.has_group(GROUP_APPROVER)

    @api.model
    def default_get(self, fields_list):
        res = super(MvComputeDiscount, self).default_get(fields_list)
        promote_discount_level = self._get_promote_discount_level()
        if promote_discount_level:
            res["level_promote_apply_for"] = promote_discount_level
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
    production_discount_policy_details_history_ids = fields.One2many(
        comodel_name="mv.partner.total.discount.detail.history",
        inverse_name="parent_id",
        string="Lịch sử chi tiết số tiền CKSL",
    )
    report_date = fields.Datetime(compute="_compute_report_date", store=True)
    approved_date = fields.Datetime(readonly=True)
    level_promote_apply_for = fields.Integer(
        "Bậc áp dụng (Khuyến khích)",
        compute="_get_promote_discount_level",
    )
    do_readonly = fields.Boolean("Readonly?", compute="set_readonly_fields")

    # =================================
    # ORM Methods
    # =================================

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
                date_str = _get_current_date_string()
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

    # =================================
    # BUSINESS Methods
    # =================================

    # [>][START] Hủy Chiết Khấu

    def action_cancel(self):
        for record in self:
            for line in record.line_ids:
                self._create_history_lines(line, "cancel")

            record.write({"state": "draft", "approved_date": False})
            record.line_ids.unlink()
            record.production_discount_policy_details_history_ids.unlink()

    # [>][END] Hủy Chiết Khấu

    # [>][START] Tính Chiết Khấu

    def action_confirm(self):
        """
        Confirms the action by ensuring necessary conditions are met,
        calculating discounts and totals, and handling sales orders and partners' information.
        """
        self.ensure_one()

        date_from, date_to = self.calculate_start_and_end_dates(
            self.report_date, self.month, self.year
        )
        self.line_ids = False
        self._invalidate_lines()

        # [>] Fetch all sale orders at once
        # Add: Filter orders that are not `returns` or `warranty claims`
        sale_orders = self._fetch_sale_orders(
            [date_from, date_to],
            [("is_order_returns", "=", False), ("is_claim_warranty", "=", False)],
        )
        if not sale_orders:
            self._raise_no_orders_error(self.month, no_orders=True)

        # [>] Filter order lines at once with the following required conditions
        order_lines = self._filter_order_lines(sale_orders)

        # [>] Get partners who are eligible for discounts
        partners = self._get_discount_eligible_partners(order_lines)

        # [>] Process partners to compute discount and total sales information
        list_line_ids = self._process_partners(
            partners, order_lines, sale_orders, date_from, date_to
        )
        if not list_line_ids:
            self._raise_no_orders_error(self.month, no_orders=False)

        # [>] Confirm the record and generate history lines
        self.write({"line_ids": list_line_ids, "state": "confirm"})
        self._generate_history_lines()

    def _raise_no_orders_error(self, month, no_orders=False):
        """Raise an error if no orders are found or no data for the given month."""
        if no_orders:
            error_message = f"Không có đơn hàng nào đã thanh toán trong tháng {month}"
        else:
            error_message = f"Không có dữ liệu để tính chiết khấu cho tháng {month}"

        raise UserError(error_message)

    def calculate_start_and_end_dates(self, report_date, target_month, target_year):
        """
        Computes the start and end dates of a given month and year.
        Args:
            target_month (str): The target month.
            target_year (str): The target year.
        Returns:
            tuple: A tuple containing the start and end dates of the given month and year.
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

    def _fetch_sale_orders(self, date_range, additional_domain=[]):
        """Fetch sale orders based on the given date range and additional domain."""
        base_sale_domain = [("state", "=", "sale")]
        if date_range:
            base_sale_domain += [
                ("date_invoice", ">=", date_range[0]),
                ("date_invoice", "<", date_range[1]),
            ]

        if additional_domain:
            base_sale_domain += additional_domain

        return self.env["sale.order"].search(base_sale_domain)

    def _filter_order_lines(self, orders):
        """Filter order lines based on the given conditions.
        - Partner must be an Agency
        - Product category is eligible for discount
        - Product type is 'product'
        - Quantity delivered is greater than 0
        - Quantity invoiced is greater than 0
        """
        return orders.order_line.filtered(
            lambda order: order.order_id.partner_id.is_agency
            and order.order_id.check_category_product(order.product_id.categ_id)
            and order.product_id.detailed_type == "product"
            and order.qty_delivered > 0
            and order.qty_invoiced > 0
            and order.discount != 100
        )

    def _get_discount_eligible_partners(self, order_lines):
        """Get partners who are eligible for discounts based on the given order lines."""
        try:
            partners = self._fetch_discount_partners(self.month, self.year)
            return order_lines.order_id.mapped("partner_id").filtered(
                lambda l: (
                    l.id in self.env["res.partner"].sudo().browse(partners.ids).ids
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

    def _process_partners(self, partners, order_lines, sale_orders, date_from, date_to):
        """Process partners to compute discount and total sales information."""
        list_line_ids = []
        report_date = self.report_date
        for partner in partners.filtered(lambda p: p.id in [140, 128, 111, 173, 212]):
            vals = self._prepare_values_for_confirmation(partner, report_date)

            OrderLines = self._get_orders_by_partner(order_lines, partner)
            vals["currency_id"] = (
                OrderLines[0].order_id.currency_id.id if OrderLines else False
            )

            OrderLines_child = self._get_orders_by_child(partner, sale_orders)
            if OrderLines_child:
                OrderLines += OrderLines_child

            sql_qty_delivered = self._compute_qty_delivered(partner, report_date)
            # Số lượng lốp đã bán (Tháng)
            vals["quantity"] = sql_qty_delivered[0]["current_month_delivered"]
            # Số lượng lốp đã bán (2 Tháng)
            vals["quantity_for_two_months"] = sql_qty_delivered[0][
                "two_months_delivered"
            ]
            # Số lượng lốp đã bán (Quý)
            vals["quantity_for_quarter"] = sql_qty_delivered[0]["quarter_delivered"]

            # [Compute Sales and Discount Levels]
            self._compute_sales_and_discounts(
                partner, OrderLines, date_from, date_to, vals
            )

            list_line_ids.append((0, 0, vals))

        return list_line_ids

    def _prepare_values_for_confirmation(self, partner, report_date):
        """Prepare values for confirmation of the given partner and report date."""
        self.ensure_one()

        return {
            "month_parent": int(report_date.month),
            "partner_id": partner.id,
            "discount_line_id": False,
            "currency_id": False,
            "level": 0,
            "sale_ids": [],
            "order_line_ids": [],
            "sale_promote_ids": [],
            "sale_return_ids": [],
            "sale_claim_warranty_ids": [],
            "quantity": 0,
            "quantity_discount": 0,
            "quantity_returns": 0,
            "quantity_claim_warranty": 0,
            "quantity_from": 0,
            "quantity_to": 0,
            "amount_total": 0,
            # Compute for a month
            "is_month": False,
            "month": 0.0,  # % chiết khấu tháng
            "month_money": 0.0,
            # Compute for 2 months
            "is_two_month": False,
            "two_months_quantity_accepted": False,
            "amount_two_month": 0.0,
            "two_month": 0.0,  # % chiết khấu 2 tháng
            "two_money": 0,
            # Compute for quarter
            "is_quarter": False,
            "quarter_quantity_accepted": False,
            "quarter": 0.0,  # % chiết khấu quý
            "quarter_money": 0,
            # Compute for year
            "is_year": False,
            "year": 0.0,  # % chiết khấu năm
            "year_money": 0,
        }

    def _get_orders_by_partner(self, order_lines, partner):
        """Get orders by partner."""
        return order_lines.filtered(lambda sol: sol.order_id.partner_id == partner)

    def _get_orders_by_child(self, partner, sale_orders):
        """Get orders by partner's children."""
        childs_of_partner = self.env["res.partner"].search(
            [("is_agency", "=", False), ("parent_id", "=", partner.id)]
        )
        return sale_orders.search(
            [("partner_id", "in", childs_of_partner.ids)]
        ).order_line.filtered(
            lambda sol: (
                sol.order_id.check_category_product(sol.product_id.categ_id)
                and sol.product_id.detailed_type == "product"
                and sol.qty_delivered > 0
                and sol.price_unit > 0
                and sol.discount != 100
            )
        )

    def _compute_qty_delivered(self, partner, report_date=None):
        """Compute the total quantity delivered."""
        query = f"""
            WITH date_params AS (
    -- Calculate start dates for previous month, current month, current quarter, and current year
    SELECT (DATE_TRUNC('month', '{report_date}'::DATE) - INTERVAL '1 month')::DATE AS previous_month_start,
           DATE_TRUNC('month', '{report_date}'::DATE)::DATE                        AS current_month_start,
           DATE_TRUNC('quarter', '{report_date}'::DATE)::DATE                      AS current_quarter_start,
           DATE_TRUNC('year', '{report_date}'::DATE)::DATE                         AS current_year_start),

     sale_orders AS (
         -- Select sale orders and sale order line IDs with various filters
         SELECT so.id,
                sol.id AS sale_line_id
         FROM sale_order_line sol
                  JOIN sale_order so ON so.id = sol.order_id
         WHERE so.state = 'sale'
           AND so.is_order_returns IS DISTINCT FROM TRUE
           AND so.is_claim_warranty IS DISTINCT FROM TRUE
           AND sol.is_service IS DISTINCT FROM TRUE
           AND sol.display_type IS NULL
           AND sol.qty_invoiced > 0
           AND sol.price_subtotal > 0
           AND sol.discount != 100
           AND sol.order_partner_id = {partner.id}),

     delivered_stock AS (
         -- Select delivered stock quantities with associated picking and move details
         SELECT sm.product_qty,
                picking_out.date_done::DATE
         FROM sale_orders so
                  JOIN stock_picking picking_out ON picking_out.sale_id = so.id
             AND picking_out.state = 'done'
                  JOIN stock_move sm ON sm.picking_id = picking_out.id
             AND sm.sale_line_id = so.sale_line_id
                  JOIN stock_picking_type spt ON spt.id = picking_out.picking_type_id
             AND spt.code = 'outgoing'),

     delivered_previous_month AS (
         -- Calculate sum of product quantities delivered in the previous month
         SELECT COALESCE(SUM(product_qty), 0) AS delivered_quantity
         FROM delivered_stock ds
                  JOIN date_params dp ON ds.date_done::DATE BETWEEN dp.previous_month_start AND dp.current_month_start),

     delivered_current_month AS (
         -- Calculate sum of product quantities delivered in the current month
         SELECT COALESCE(SUM(product_qty), 0) AS delivered_quantity
         FROM delivered_stock ds
                  JOIN date_params dp ON ds.date_done::DATE BETWEEN dp.current_month_start
             AND dp.current_month_start + INTERVAL '1 month - 1 day'),

     delivered_two_months AS (
         -- Calculate sum of product quantities delivered in the last two months
         SELECT COALESCE(SUM(product_qty), 0) AS delivered_quantity
         FROM delivered_stock ds
                  JOIN date_params dp ON ds.date_done::DATE BETWEEN dp.previous_month_start
             AND dp.current_month_start + INTERVAL '1 month - 1 day'),

     delivered_quarter AS (
         -- Calculate sum of product quantities delivered in the current quarter
         SELECT COALESCE(SUM(product_qty), 0) AS delivered_quantity
         FROM delivered_stock ds
                  JOIN date_params dp ON ds.date_done::DATE BETWEEN dp.current_quarter_start
             AND dp.current_quarter_start + INTERVAL '3 month - 1 day'),

     delivered_current_year AS (
         -- Calculate sum of product quantities delivered in the current year
         SELECT COALESCE(SUM(product_qty), 0) AS delivered_quantity
         FROM delivered_stock ds
                  JOIN date_params dp ON ds.date_done::DATE BETWEEN dp.current_year_start
             AND dp.current_year_start + INTERVAL '1 year - 1 day')

-- Select final delivered quantities breakdown by time periods
SELECT (SELECT delivered_quantity FROM delivered_previous_month) AS previous_month_delivered,
       (SELECT delivered_quantity FROM delivered_current_month)  AS current_month_delivered,
       (SELECT delivered_quantity FROM delivered_two_months)     AS two_months_delivered,
       (SELECT delivered_quantity FROM delivered_quarter)        AS quarter_delivered,
       (SELECT delivered_quantity FROM delivered_current_year)   AS year_delivered
        """
        self.env.cr.execute(query)
        return self.env.cr.dictfetchall()

    def _compute_sales_and_discounts(
        self, partner, order_lines, date_from, date_to, vals
    ):
        """Compute sales and applicable discounts for the partner."""
        total_sales = sum(order_lines.mapped("price_subtotal_before_discount"))
        vals["amount_total"] = total_sales

        appropriate_discount = partner.line_ids.filtered(
            lambda discount: (
                date.today() >= discount.date if discount.date else not discount.date
            )
        ).sorted("level")

        if appropriate_discount:
            level = appropriate_discount[-1].level
            discount_id = appropriate_discount[-1].parent_id
            discount_line_id = discount_id.line_ids.filtered(
                lambda rec: rec.level == level
            )

            vals["level"] = discount_line_id.level
            vals["quantity_from"] = discount_line_id.quantity_from
            vals["quantity_to"] = discount_line_id.quantity_to

            # [>] === Để đạt được chỉ tiêu 1 tháng ===
            # => Chỉ cần thỏa số lượng trong tháng
            self._compute_monthly_discount(discount_line_id, total_sales, vals)

            # [>] === Để đạt kết quả 2 tháng ===
            # =>Tháng này phải đạt chỉ tiêu tháng & tháng trước phải đạt chỉ tiêu tháng và chưa đạt chỉ tiêu 2 tháng
            self._compute_two_month_discount(
                partner, discount_line_id, total_sales, vals
            )

            # [>] === Để đạt kết quả quý [1, 2, 3] [4, 5, 6] [7, 8, 9] [10, 11, 12] ===
            # => Chỉ xét quý vào các tháng 3 6 9 12, chỉ cần kiểm tra 2 tháng trước đó có đạt chỉ tiêu tháng ko
            self._compute_quarterly_discount(
                partner, discount_line_id, total_sales, vals
            )

            # [>] === Để đạt kết quả năm thì tháng đang xét phải là 12 ===
            # => Kiểm tra 11 tháng trước đó đã được chỉ tiêu tháng chưa
            self._compute_yearly_discount(partner, discount_line_id, total_sales, vals)

            sale_ids = order_lines.mapped("order_id").ids
            vals["sale_ids"] = sale_ids
            vals["order_line_ids"] = order_lines.ids
            vals["discount_line_id"] = discount_line_id.id

            # Fetch additional data for promotions, returns, and claims
            self._fetch_additional_data(partner, date_from, date_to, vals)

    def _compute_monthly_discount(self, discount_line_id, total_sales, vals):
        """Compute monthly discount details."""
        vals["is_month"] = vals["quantity"] >= vals["quantity_from"]
        if vals["is_month"]:
            vals["month"] = discount_line_id.month
            vals["month_money"] = total_sales * discount_line_id.month / 100

    def _compute_two_month_discount(self, partner, discount_line_id, total_sales, vals):
        """Compute two-month discount details."""
        if self.month == "1":
            previous_month = "12"
            previous_year = str(int(self.year) - 1)
        else:
            previous_month = str(int(self.month) - 1)
            previous_year = self.year

        qty_min_by_lv = discount_line_id.quantity_from or vals["quantity_from"]
        quantity_for_two_months = vals["quantity_for_two_months"]
        previous_discount = self.env["mv.compute.discount.line"].search(
            [
                ("partner_id", "=", partner.id),
                ("name", "=", previous_month + "/" + previous_year),
                ("is_month", "=", True),
            ]
        )
        if previous_discount and not previous_discount.is_two_month:
            vals["is_two_month"] = True
            vals["two_months_quantity_accepted"] = True
            vals["two_month"] = discount_line_id.two_month
            vals["amount_two_month"] = previous_discount.amount_total + total_sales
            vals["two_money"] = (
                vals["amount_two_month"] * discount_line_id.two_month / 100
            )

    def _compute_quarterly_discount(self, partner, discount_line_id, total_sales, vals):
        """Compute quarterly discount details."""
        qty_min_by_lv = discount_line_id.quantity_from or vals["quantity_from"]
        quantity_for_quarter = vals["quantity_for_quarter"]
        previous_months = [
            str(int(self.month) - i) + "/" + self.year for i in range(1, 3)
        ]
        previous_months_discount = self.env["mv.compute.discount.line"].search(
            [
                ("partner_id", "=", partner.id),
                ("name", "in", previous_months),
                ("is_month", "=", True),
            ]
        )
        if (
            self.month in QUARTER_OF_YEAR
            and not previous_months_discount
            and quantity_for_quarter > int(qty_min_by_lv) * 3
        ):
            vals["is_quarter"] = True
            vals["quarter_quantity_accepted"] = True
            vals["quarter"] = discount_line_id.quarter
            vals["quarter_money"] = (
                (
                    total_sales
                    + previous_months_discount[0].amount_total
                    + previous_months_discount[1].amount_total
                )
                * discount_line_id.quarter
                / 100
            )

    def _compute_yearly_discount(self, partner, discount_line_id, total_sales, vals):
        """Compute yearly discount details."""
        if self.month == DECEMBER:
            yearly_flag = True
            yearly_total = 0
            for i in range(1, 13):
                month_name = str(i) + "/" + self.year
                monthly_line = self.env["mv.compute.discount.line"].search(
                    [
                        ("partner_id", "=", partner.id),
                        ("name", "=", month_name),
                        ("is_month", "=", True),
                    ]
                )
                if not monthly_line:
                    yearly_flag = False
                yearly_total += monthly_line.amount_total

            if yearly_flag:
                vals["is_year"] = True
                vals["year"] = discount_line_id.quarter
                vals["year_money"] = yearly_total * discount_line_id.quarter / 100

    def _fetch_additional_data(self, partner, date_from, date_to, vals):
        """Fetch additional data like promotions, returns, and claims."""
        model_load_data = self.env["mv.compute.discount.line"].sudo()

        vals["sale_promote_ids"], sale_promote_quantity = self._fetch_sale_promote_data(
            partner, date_from, date_to, model_load_data
        )
        vals["quantity_discount"] = sale_promote_quantity

        vals["sale_return_ids"], sale_returns_quantity = self._fetch_sale_return_data(
            partner, date_from, date_to, model_load_data
        )
        vals["quantity_returns"] = sale_returns_quantity

        vals["sale_claim_warranty_ids"], sale_claim_warranty_quantity = (
            self._fetch_sale_claim_data(partner, date_from, date_to, model_load_data)
        )
        vals["quantity_claim_warranty"] = sale_claim_warranty_quantity

    def _fetch_sale_promote_data(self, partner, date_from, date_to, model_load_data):
        """Fetch sales promotion data."""
        sale_promote_ids = self.env["sale.order"].browse(
            model_load_data._sql_get_sale_promote_ids(
                partner_id=partner, date_from=date_from.date(), date_to=date_to.date()
            )[0]
        )
        sale_promote_quantity = model_load_data._sql_get_sale_promote_ids(
            partner_id=partner, date_from=date_from.date(), date_to=date_to.date()
        )[1]
        return (
            [(6, 0, self.env["sale.order"].browse(sale_promote_ids.ids).ids or [])],
            sale_promote_quantity,
        )

    def _fetch_sale_return_data(self, partner, date_from, date_to, model_load_data):
        """Fetch sales return data."""
        sale_returns_ids = self.env["sale.order"].browse(
            model_load_data._sql_get_sale_return_ids(
                partner_id=partner, date_from=date_from.date(), date_to=date_to.date()
            )[0]
        )
        sale_returns_quantity = model_load_data._sql_get_sale_return_ids(
            partner_id=partner, date_from=date_from.date(), date_to=date_to.date()
        )[1]
        return (
            [(6, 0, self.env["sale.order"].browse(sale_returns_ids.ids).ids or [])],
            sale_returns_quantity,
        )

    def _fetch_sale_claim_data(self, partner, date_from, date_to, model_load_data):
        """Fetch sales claim warranty data."""
        sale_claim_warranty_ids = self.env["sale.order"].browse(
            model_load_data._sql_get_sale_claim_warranty_ids(
                partner_id=partner, date_from=date_from.date(), date_to=date_to.date()
            )[0]
        )
        sale_claim_warranty_quantity = model_load_data._sql_get_sale_claim_warranty_ids(
            partner_id=partner, date_from=date_from.date(), date_to=date_to.date()
        )[1]
        return (
            [
                (
                    6,
                    0,
                    self.env["sale.order"].browse(sale_claim_warranty_ids.ids).ids
                    or [],
                )
            ],
            sale_claim_warranty_quantity,
        )

    def _generate_history_lines(self):
        """Generate history lines based on confirmed records."""
        for record in self.line_ids.filtered(lambda rec: rec.parent_id):
            self._create_history_lines(record, "confirm")

    # [>][END] Tính Chiết Khấu

    # [>][START] Duyệt Chiết Khấu

    def action_approve(self):
        if not self._has_approval_access(self.env):
            raise AccessError("Bạn không có quyền duyệt!")

        base_total_detail_histories = self._fetch_base_total_detail_histories()

        for record in self.filtered(lambda r: len(r.line_ids) > 0):
            partners_updates = self._calculate_partners_updates(record)
            self._update_partner_amounts(partners_updates)

            self._create_history_lines(record, "approve")

            if record.id not in base_total_detail_histories.mapped("parent_id").ids:
                record.create_total_discount_detail_history()

            record.write({"state": "done", "approved_date": fields.Datetime.now()})

    def _fetch_base_total_detail_histories(self):
        return self.env["mv.partner.total.discount.detail.history"].search(
            [("partner_id", "in", self.line_ids.mapped("partner_id").ids)]
        )

    def _calculate_partners_updates(self, record):
        updates = {}
        for discount_line in record.line_ids:
            partner_id = discount_line.partner_id.id
            total_money = discount_line.total_money
            updates[partner_id] = updates.get(partner_id, 0) + total_money
        return updates

    def _update_partner_amounts(self, partners_updates):
        for partner_id, total_money in partners_updates.items():
            partner = self.env["res.partner"].sudo().browse(partner_id)
            partner.write({"amount": partner.amount + total_money})

    # [>][END] Duyệt Chiết Khấu

    # [>][START]  Ghi nhận Lịch Sử Chiết Khấu Sản Lượng theo Tháng

    def create_total_discount_detail_history(self):
        for line in self.line_ids.filtered(lambda l: l.parent_id):
            self.env[
                "mv.partner.total.discount.detail.history"
            ]._create_total_discount_detail_history_line(parent_id=self, policy_id=line)

    def _create_history_lines(self, record, type):
        if type == "confirm":
            self._create_confirm_history_lines(record)
        elif type == "approve":
            self._create_approve_history_lines(record)
        elif type == "cancel":
            self._create_cancel_history_lines(record)

    def _prepare_histories_data(self, line, message, optional_values):
        """Prepare values to create a history line for the Partner Agency that has calculated the discount.

        :param optional_values: any parameter that should be added to the returned history line
        :rtype: dict
        """
        self.ensure_one()

        compute_sudo = line.sudo()
        history_description = message
        history_date = (
            compute_sudo.parent_id.approved_date or compute_sudo.parent_id.write_date
        )
        history_user_action_id = compute_sudo.parent_id.write_uid.id
        res = {
            "partner_id": compute_sudo.partner_id.id,
            "history_description": history_description,
            "history_date": history_date,
            "history_user_action_id": history_user_action_id,
            "production_discount_policy_id": compute_sudo.id,
            "production_discount_policy_total_money": compute_sudo.total_money,
        }
        if optional_values:
            res = res | optional_values
        return res

    def _create_confirm_history_lines(self, line):
        self.ensure_one()

        values = self._prepare_histories_data(
            line=line,
            message=f"Chiết khấu sản lượng tháng {line.name} đang chờ duyệt.",
            optional_values={
                "total_money": line.total_money,
                "total_money_discount_display": (
                    "+ {:,.2f}".format(line.total_money)
                    if line.total_money > 0
                    else "{:,.2f}".format(line.total_money)
                ),
                "is_waiting_approval": line.total_money > 0,
                "is_positive_money": False,
                "is_negative_money": False,
            },
        )
        self.env["mv.discount.partner.history"].create(values)

    def _create_approve_history_lines(self, line):
        self.ensure_one()

        values = self._prepare_histories_data(
            line,
            message=f"Chiết khấu sản lượng tháng {line.name} đã được duyệt.",
            optional_values={
                "total_money": line.total_money,
                "total_money_discount_display": (
                    "+ {:,.2f}".format(line.total_money)
                    if line.total_money > 0
                    else "{:,.2f}".format(line.total_money)
                ),
                "is_positive_money": line.total_money > 0,
                "is_waiting_approval": False,
                "is_negative_money": False,
            },
        )
        self.env["mv.discount.partner.history"]._create_history_line(**values)

    def _create_cancel_history_lines(self, line):
        self.ensure_one()

        values = self._prepare_histories_data(
            line,
            message=f"Chiết khấu sản lượng tháng {line.name} đã bị từ chối, đang chờ xem xét.",
            optional_values={
                "total_money": line.total_money,
                "total_money_discount_display": (
                    "- {:,.2f}".format(line.total_money)
                    if line.total_money > 0
                    else "{:,.2f}".format(line.total_money)
                ),
                "is_negative_money": line.total_money > 0,
                "is_waiting_approval": False,
                "is_positive_money": False,
            },
        )
        self.env["mv.discount.partner.history"]._create_history_line(**values)

    # [>][END]  Ghi nhận Lịch Sử Chiết Khấu Sản Lượng theo Tháng

    def _get_views(self):
        return [
            [self.env.ref("mv_sale.mv_compute_discount_line_tree").id, "tree"],
            [self.env.ref("mv_sale.mv_compute_discount_line_form").id, "form"],
        ]

    def _get_context(self):
        return {
            "create": False,
            "edit": False,
            "tree_view_ref": "mv_sale.mv_compute_discount_line_tree",
            "form_view_ref": "mv_sale.mv_compute_discount_line_form",
            "search_default_filter_partner_sales_state": True,
        }

    def action_view_tree(self):
        view_name = f"Kết quả chiết khấu của tháng: {self.name}"
        return {
            "type": "ir.actions.act_window",
            "name": view_name,
            "res_model": "mv.compute.discount.line",
            "view_mode": "tree,form",
            "views": self._get_views(),
            "search_view_id": [
                self.env.ref("mv_sale.mv_compute_discount_line_search_view").id,
                "search",
            ],
            "domain": [("parent_id", "=", self.id)],
            "context": self._get_context(),
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
                       cdl.quantity_returns                   AS quantity_returns,
                       cdl.quantity_claim_warranty                   AS quantity_claim_warranty,
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
                    "quantity_returns": data["quantity_returns"],
                    "quantity_claim_warranty": data["quantity_claim_warranty"],
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
        sheet.merge_range("A1:O1", "", DEFAULT_FORMAT)
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

        # ////// NAME = "Số lượng lốp Đổi Trả (Cái)"
        sheet.merge_range("G2:G3", "", DEFAULT_FORMAT)
        sheet.write("G2", "SL lốp đổi trả (Cái)", SUB_TITLE_FORMAT)

        # ////// NAME = "Số lượng lốp Bảo Hành (Cái)"
        sheet.merge_range("H2:H3", "", DEFAULT_FORMAT)
        sheet.write("H2", "SL lốp bảo hành (Cái)", SUB_TITLE_FORMAT)

        # ////// NAME = "Doanh thu Tháng"
        sheet.merge_range("I2:I3", "", DEFAULT_FORMAT)
        sheet.write("I2", "Doanh thu", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu tháng"
        sheet.merge_range("J2:J3", "", DEFAULT_FORMAT)
        sheet.write("J2", "Tiền CK Tháng", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu 2 tháng"
        sheet.merge_range("K2:K3", "", DEFAULT_FORMAT)
        sheet.write("K2", "Tiền CK 2 Tháng", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu quý"
        sheet.merge_range("L2:L3", "", DEFAULT_FORMAT)
        sheet.write("L2", "Tiền CK Quý", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu năm"
        sheet.merge_range("M2:M3", "", DEFAULT_FORMAT)
        sheet.write("M2", "Tiền CK Năm", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu khuyến khích"
        sheet.merge_range("N2:N3", "", DEFAULT_FORMAT)
        sheet.write("N2", "Tiền CK Khuyến Khích", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Tổng tiền chiết khấu"
        sheet.merge_range("O2:O3", "", DEFAULT_FORMAT)
        sheet.write("O2", "Tổng tiền", SUB_TITLE_TOTAL_FORMAT)

        sheet.set_column(4, 14, 15)

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
                    if col in [8, 9, 10, 11, 12, 13, 14]:
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
