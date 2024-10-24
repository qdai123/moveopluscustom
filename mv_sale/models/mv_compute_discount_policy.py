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


POLICY_APPROVER = "mv_sale.group_mv_compute_discount_approver"


class MvComputeDiscountPolicy(models.Model):
    _name = "mv.compute.discount.policy"
    _description = "CHIẾT KHẤU GIẢM GIÁ cho Đại lý"
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
    discount_policy_id = fields.Many2one(
        "mv.discount.policy",
        required=True,
        domain=[("active", "=", True), ("policy_status", "=", "applying")],
        default=lambda self: self.env["mv.discount.policy"].search(
            [("active", "=", True), ("policy_status", "=", "applying")], limit=1
        ),
    )
    line_ids = fields.One2many("mv.compute.discount.policy.line", "parent_id")
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

    @api.constrains("discount_policy_id", "month", "year")
    def _validate_discount_policy_already_exist(self):
        for policy in self:
            if policy.discount_policy_id and policy.month and policy.year:
                policy_exist = self.env["mv.compute.discount.policy"].search_count(
                    [
                        ("id", "!=", policy.id),
                        ("discount_policy_id", "=", policy.discount_policy_id.id),
                        ("month", "=", policy.month),
                        ("year", "=", policy.year),
                    ]
                )
                if policy_exist > 0:
                    raise ValidationError(
                        f"Chính sách của {policy.month}/{policy.year} đã được tạo hoặc đã được tính toán rồi!"
                    )

    @api.constrains("report_date", "discount_policy_id")
    def _validate_time_frame_of_discount_policy(self):
        for policy_compute in self:
            if policy_compute.discount_policy_id and policy_compute.report_date:
                policy = policy_compute.discount_policy_id
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
        self.env["mv.compute.discount.policy.line"].search(
            [("parent_id", "in", self.ids)]
        ).unlink()

        return super(MvComputeDiscountPolicy, self).unlink()

    # =================================
    # BUSINESS Methods
    # =================================

    def action_confirm(self):
        """Confirm the record and compute the discount policy."""
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
            self._raise_no_orders_error(self.month, self.year, no_orders=True)

        # [>] Filter order lines at once with the following required conditions
        order_lines = self._filter_order_lines(sale_orders)

        # [>] Get partners who are eligible for discounts
        partners = self._get_discount_eligible_partners(order_lines)

        # [>] Process partners to compute discount and total sales information
        list_line_ids = self._process_partners(partners, order_lines, sale_orders)
        if not list_line_ids:
            self._raise_no_orders_error(self.month, self.year, no_orders=False)

        # [>] Confirm the record and update the line_ids
        self.write({"line_ids": list_line_ids, "state": "confirm"})

    def _raise_no_orders_error(self, month, year, no_orders=False):
        """Raise an error if no orders are found or no data for the given month."""
        if no_orders:
            error_message = (
                f"Không có đơn hàng nào đã thanh toán trong tháng {month}/{year}"
            )
        else:
            error_message = (
                f"Không có dữ liệu để tính chiết khấu cho tháng {month}/{year}"
            )

        raise UserError(error_message)

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

    def _filter_order_lines(self, sale_orders=[]):
        """Filter order lines based on the given conditions.
        - Partner must be an Agency
        - Product category is eligible for discount
        - Product type is 'product'
        - Quantity delivered is greater than 0
        - Quantity invoiced is greater than 0
        """
        if not sale_orders:
            return self.env["sale.order.line"]  # Return empty recordset

        return sale_orders.order_line.filtered(
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

    def _process_partners(self, partners, order_lines, sale_orders):
        """Process partners to compute discount information."""

        if not self.discount_policy_id:
            raise UserError("Không tìm thấy chính sách chiết khấu!")

        list_line_ids = []
        report_date = self.report_date
        for partner in partners:
            vals = self._prepare_values_for_confirmation(partner, report_date)

            OrderLines = self._get_orders_by_partner(order_lines, partner)
            OrderLines_child = self._get_orders_by_child(partner, sale_orders)
            if OrderLines_child:
                OrderLines += OrderLines_child

            products = self._compute_qty_delivered(partner, report_date)
            list_products_accepted = [
                product_accepted
                for product_accepted in products.items()
                if product_accepted[0]
                in self.discount_policy_id.policy_product_level_ids.mapped(
                    "product_id"
                ).ids
            ]

            self._compute_product_level_lines(
                policy_id=self.discount_policy_id.id,
                order_lines=OrderLines,
                products=list_products_accepted,
                vals=vals,
            )

            list_line_ids.append((0, 0, vals))

        return list_line_ids

    def _prepare_values_for_confirmation(self, partner, report_date):
        """Prepare values for confirmation of the given partner and report date."""
        self.ensure_one()

        return {
            "parent_id": self.id,
            "compute_date": report_date,
            "partner_id": partner.id,
            "currency_id": partner.company_id.sudo().currency_id
            or self.env.company.currency_id.id,
            "product_level_line_ids": [],
        }

    def _get_orders_by_partner(self, order_lines, partner):
        """Get orders by partner."""
        return order_lines.filtered(
            lambda sol: sol.order_id.partner_id.id == partner.id
        )

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
         SELECT sm.product_id                             AS product,
                     COALESCE(sm.product_qty, 0)    AS delivered_quantity
         FROM sale_orders so
                    JOIN stock_picking picking_out ON picking_out.sale_id = so.id
             AND picking_out.state = 'done'
                    JOIN stock_move sm ON sm.picking_id = picking_out.id
             AND sm.sale_line_id = so.sale_line_id
                    JOIN stock_picking_type spt ON spt.id = picking_out.picking_type_id
             AND spt.code = 'outgoing'
                    JOIN date_params dp ON picking_out.date_done::DATE BETWEEN dp.current_month_start
             AND dp.current_month_start + INTERVAL '1 month - 1 day'
         ORDER BY product)

-- Select final delivered quantities
SELECT * FROM delivered_stock;
        """
        self.env.cr.execute(query)
        products = dict(
            (
                (r["product"], r["delivered_quantity"])
                for r in self.env.cr.dictfetchall()
            )
        )
        return products

    def _compute_product_level_lines(self, policy_id, order_lines, products, vals):
        """Compute the product level lines based on the given order lines."""

        policy = self.env["mv.discount.policy"].browse(policy_id)
        policy_level_quantity_list = policy.policy_level_quantity_ids
        policy_product_level_list = policy.policy_product_level_ids

        def _determine_policy_level(quantity):
            """Determine the policy level to apply based on total quantity."""
            level_idx = 0
            while level_idx <= len(policy_level_quantity_list) - 1:
                if (
                    policy_level_quantity_list[level_idx].quantity_min
                    <= quantity
                    <= policy_level_quantity_list[level_idx].quantity_max
                ):
                    return policy_level_quantity_list[level_idx].level
                level_idx += 1
            return 0

        products_dict = {product[0]: product for product in products}
        for order_product in order_lines.mapped("product_id"):
            product = products_dict.get(order_product.id)
            if product:
                product_level_policy = policy_product_level_list.filtered(
                    lambda p: p.product_id.id == order_product.id
                )
                total_qty = product[1]
                policy_level_apply = _determine_policy_level(total_qty)
                not_discount = policy_level_apply == 0
                if 1 <= policy_level_apply < len(policy_level_quantity_list) + 1:
                    price_level = getattr(
                        product_level_policy, f"price_level_{policy_level_apply}", 0
                    )
                    product_vals = {
                        "not_discount": not_discount,
                        "product_id": order_product.id,
                        "product_template_id": order_product.product_tmpl_id.id,
                        "total_quantity": total_qty,
                        f"total_price_level_{policy_level_apply}": price_level,
                    }
                    vals["product_level_line_ids"].append((0, 0, product_vals))

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
            total_money = compute_line.total_price_discount
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


class MvComputeDiscountPolicyLine(models.Model):
    _name = _description = "mv.compute.discount.policy.line"

    parent_id = fields.Many2one(
        "mv.compute.discount.policy",
        domain=[("active", "=", True)],
        readonly=True,
    )
    name = fields.Char(compute="_compute_parent_name", store=True)
    state = fields.Selection(related="parent_id.state", store=True, readonly=True)
    compute_date = fields.Datetime(readonly=True)
    partner_id = fields.Many2one("res.partner", "Đại lý", readonly=True)
    partner_discount_name = fields.Char(
        compute="_define_partner_discount_name", string="Đại lý"
    )
    partner_company_ref = fields.Char(
        related="partner_id.company_registry",
        string="Mã đại lý",
        store=True,
    )
    product_level_line_ids = fields.One2many(
        "mv.compute.product.level.line",
        "discount_policy_line_id",
        string="Sản phẩm",
    )
    currency_id = fields.Many2one("res.currency", readonly=True)
    total_quantity = fields.Integer(compute="_compute_total_quantity", store=True)
    total_price_discount = fields.Monetary(
        compute="_compute_total_price_discount",
        store=True,
        currency_field="currency_id",
    )

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

    @api.depends("product_level_line_ids")
    def _compute_total_quantity(self):
        for line in self:
            line.total_quantity = sum(
                [product.total_quantity for product in line.product_level_line_ids]
            )

    @api.depends("product_level_line_ids")
    def _compute_total_price_discount(self):
        for line in self:
            line.total_price_discount = sum(
                [
                    product.total_price_all_level
                    for product in line.product_level_line_ids
                ]
            )

    @api.depends("partner_id", "product_level_line_ids")
    def _define_partner_discount_name(self):
        for line in self:
            if line.partner_id and line.product_level_line_ids:
                line.partner_discount_name = (
                    line.partner_id.name + f" ({len(line.product_level_line_ids)})"
                )
            else:
                line.partner_discount_name = line.partner_id.name

    @api.autovacuum
    def _gc_compute_discount_policy_line(self):
        """Delete all lines that are not linked to the parent."""
        lines_to_del = self.env[self._name].search([("parent_id", "=", False)])
        if lines_to_del:
            lines_to_del.unlink()
            _logger.info("Successfully deleted unlinked policy lines.")
        else:
            _logger.info("No unlinked policy lines found.")


class MvComputeProductLevelLine(models.Model):
    _name = _description = "mv.compute.product.level.line"

    discount_policy_line_id = fields.Many2one(
        "mv.compute.discount.policy.line",
        readonly=True,
        ondelete="cascade",
    )
    currency_id = fields.Many2one(
        "res.currency",
        related="discount_policy_line_id.currency_id",
        store=True,
    )
    product_id = fields.Many2one("product.product", readonly=True)
    product_template_id = fields.Many2one(
        "product.template",
        "Sản phẩm",
        readonly=True,
    )
    update_count = fields.Integer("Số lần cập nhật", default=0)
    not_discount = fields.Boolean("Không chiết khấu", default=False)
    total_quantity = fields.Integer(readonly=True)
    total_price_level_1 = fields.Monetary("Level 1", currency_field="currency_id")
    total_price_level_2 = fields.Monetary("Level 2", currency_field="currency_id")
    total_price_level_3 = fields.Monetary("Level 3", currency_field="currency_id")
    total_price_level_4 = fields.Monetary("Level 4", currency_field="currency_id")
    total_price_level_5 = fields.Monetary("Level 5", currency_field="currency_id")
    total_price_all_level = fields.Monetary(
        compute="_compute_total_price_discount",
        store=True,
        string="Total",
    )
    # Technical computed fields for UX purposes (hide/make fields readonly, ...)
    product_line_updatable = fields.Boolean(
        string="Can Edit Product", compute="_compute_product_updatable"
    )

    @api.depends("discount_policy_line_id")
    def _compute_product_updatable(self):
        for line in self:
            line.product_line_updatable = (
                line.discount_policy_line_id
                and line.discount_policy_line_id.state != "done"
            )

    @api.depends(
        "total_quantity",
        "total_price_level_1",
        "total_price_level_2",
        "total_price_level_3",
        "total_price_level_4",
        "total_price_level_5",
    )
    def _compute_total_price_discount(self):
        for product in self:
            product.total_price_all_level = (
                sum(
                    [
                        product.total_price_level_1,
                        product.total_price_level_2,
                        product.total_price_level_3,
                        product.total_price_level_4,
                        product.total_price_level_5,
                    ]
                )
                * product.total_quantity
            )

    def update_product_price_level(self):
        self.ensure_one()
        return {
            "name": "Cập nhật cho sản phẩm: %s" % self.product_template_id.name,
            "type": "ir.actions.act_window",
            "res_model": "mv.wizard.update.product.price.level",
            "view_mode": "form",
            "view_id": self._get_view_id(),
            "context": self._get_context(),
            "target": "new",
        }

    def _get_view_id(self):
        return self.env.ref("mv_sale.mv_wizard_update_product_price_level_form_view").id

    def _get_context(self):
        return {
            "default_discount_policy_line_id": self.discount_policy_line_id.id,
            "default_discount_product_level_line_id": self.id,
            "default_product_id": self.product_id.id,
            "default_product_template_id": self.product_template_id.id,
            "default_old_total_price_level_1": self.total_price_level_1,
            "default_new_total_price_level_1": self.total_price_level_1,
            "default_old_total_price_level_2": self.total_price_level_2,
            "default_new_total_price_level_2": self.total_price_level_2,
            "default_old_total_price_level_3": self.total_price_level_3,
            "default_new_total_price_level_3": self.total_price_level_3,
            "default_old_total_price_level_4": self.total_price_level_4,
            "default_new_total_price_level_4": self.total_price_level_4,
            "default_old_total_price_level_5": self.total_price_level_5,
            "default_new_total_price_level_5": self.total_price_level_5,
        }

    @api.autovacuum
    def _gc_compute_product_level_line(self):
        """Delete all lines that are not linked to the parent."""
        lines_to_del = self.env[self._name].search(
            [("discount_policy_line_id", "=", False)]
        )
        if lines_to_del:
            lines_to_del.unlink()
            _logger.info("Successfully deleted unlinked policy lines.")
        else:
            _logger.info("No unlinked policy lines found.")
