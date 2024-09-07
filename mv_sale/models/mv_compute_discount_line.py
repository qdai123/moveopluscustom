# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools.misc import formatLang

GROUP_APPROVER = "mv_sale.group_mv_compute_discount_approver"


class MvComputeDiscountLine(models.Model):
    _name = "mv.compute.discount.line"
    _description = _("Compute Discount (%) Line for Partner Agency")
    _rec_name = "partner_id"

    # === FIELDS ===#
    parent_id = fields.Many2one("mv.compute.discount", "Chính sách chiết khấu")
    discount_line_id = fields.Many2one(
        "mv.discount.line", "Chính sách chiết khấu chi tiết"
    )
    name = fields.Char(related="parent_id.name", store=True)
    state = fields.Selection(related="parent_id.state", store=True, readonly=True)
    month_parent = fields.Integer("Tháng")
    currency_id = fields.Many2one(
        "res.currency",
        "Tiền tệ",
        compute="_get_company_currency",
        store=True,
    )
    partner_id = fields.Many2one("res.partner", "Đại lý")
    partner_sales_state = fields.Selection(
        [
            ("qualified", "Đạt"),
            ("imqualified", "Chưa Đạt"),
            ("qualified_by_approving", "Duyệt cho Đạt"),
        ],
        "Đạt/Chưa Đạt",
        compute="_compute_partner_sales_state",
        store=True,
    )
    level = fields.Integer("Bậc")
    basic = fields.Float("Cơ bản (%)")
    quantity = fields.Integer("Số lượng lốp đã bán")
    quantity_discount = fields.Integer("Số lượng lốp khuyến mãi")
    quantity_returns = fields.Integer("Số lượng lốp đổi trả")
    quantity_claim_warranty = fields.Integer("Số lượng lốp bảo hành")
    quantity_from = fields.Integer("Số lượng lốp min")
    quantity_to = fields.Integer("Số lượng lốp max")

    # SALES Fields:
    sale_ids = fields.One2many(
        "sale.order",
        "discount_line_id",
        string="Đơn hàng",
        help="Danh sách đơn hàng trong tháng của đại lý",
    )
    order_line_ids = fields.One2many(
        "sale.order.line",
        "discount_line_id",
        string="Dòng đơn hàng",
        help="Chi tiết đơn hàng trong tháng của đại lý",
    )
    sale_promote_ids = fields.Many2many(
        "sale.order",
        "sale_promote_discount_rel",
        "discount_line_id",
        "sale_id",
        string="Đơn hàng khuyến khích",
        help="Danh sách đơn hàng khuyến khích trong tháng của đại lý",
    )
    sale_return_ids = fields.Many2many(
        "sale.order",
        "sale_returns_discount_rel",
        "discount_line_id",
        "sale_id",
        string="Đơn hàng trả",
        help="Danh sách đơn hàng trả trong tháng của đại lý",
    )
    sale_claim_warranty_ids = fields.Many2many(
        "sale.order",
        "sale_claim_warranty_discount_rel",
        "discount_line_id",
        "sale_id",
        string="Đơn hàng bảo hành",
        help="Danh sách đơn hàng bảo hành trong tháng của đại lý",
    )

    # TOTAL Fields:
    opening_balance = fields.Monetary("Số dư đầu kỳ")
    closing_balance = fields.Monetary("Số dư cuối kỳ")
    amount_total = fields.Float("Doanh thu tháng")
    total_discount = fields.Float("Total % Discount")
    total_money = fields.Integer(
        "Tổng tiền chiết khấu ",
        compute="_compute_total_money",
        store=True,
    )

    # Chiết Khấu 1 Tháng
    is_month = fields.Boolean()
    month = fields.Float("% chiết khấu tháng", digits=(16, 2))
    month_money = fields.Integer("Số tiền chiết khấu tháng")

    # Chiết Khấu 2 Tháng
    is_two_month = fields.Boolean()
    amount_two_month = fields.Float("Số tiền 2 Tháng")
    two_month = fields.Float("% chiết khấu 2 tháng", digits=(16, 2))
    two_money = fields.Integer("Số tiền chiết khấu 2 tháng")

    # Chiết Khấu Quý
    is_quarter = fields.Boolean()
    quarter = fields.Float("% chiết khấu quý", digits=(16, 2))
    quarter_money = fields.Integer("Số tiền chiết khấu quý")

    # Chiết Khấu Năm
    is_year = fields.Boolean()
    year = fields.Float("% chiết khấu năm", digits=(16, 2))
    year_money = fields.Integer("Số tiền chiết khấu năm")

    # Chiết Khấu Khuyến Khích
    is_promote_discount = fields.Boolean()
    promote_discount_percentage = fields.Float(
        "% chiết khấu khuyến khích", digits=(16, 2)
    )
    promote_discount_money = fields.Float("Số tiền chiết khấu khuyến khích")

    def _get_company_currency(self):
        for record in self:
            if record.partner_id.company_id:
                record.currency_id = record.partner_id.sudo().company_id.currency_id
            else:
                record.currency_id = self.env.company.currency_id

    @api.depends("quantity", "quantity_from")
    def _compute_partner_sales_state(self):
        for record in self.filtered(
            lambda r: r.partner_sales_state not in ["qualified_by_approving"]
        ):
            if record.quantity >= record.quantity_from:
                record.partner_sales_state = "qualified"
            else:
                record.partner_sales_state = "imqualified"

    @api.depends(
        "month_money",
        "two_money",
        "quarter_money",
        "year_money",
        "promote_discount_money",
    )
    def _compute_total_money(self):
        for record in self:
            record.total_money = (
                record.month_money
                + record.two_money
                + record.quarter_money
                + record.year_money
                + record.promote_discount_money
            )

    # =================================
    # BUSINESS Methods
    # =================================

    def action_approve_for_promote(self):
        self.ensure_one()

        if not self._access_approve():
            raise AccessError("Bạn không có quyền duyệt!")

        return {
            "type": "ir.actions.act_window",
            "name": "Vui lòng chọn % chiết khấu Khuyến Khích cho Đại lý",
            "res_model": "mv.wizard.promote.discount.line",
            "views": [
                [
                    self.env.ref(
                        "mv_sale.mv_wizard_promote_discount_line_form_view"
                    ).id,
                    "form",
                ]
            ],
            "domain": [],
            "context": {
                "default_compute_discount_line_id": self.id,
                "default_compute_discount_id": self.parent_id.id,
                "default_partner_id": self.partner_id.id,
            },
            "target": "new",
        }

    def action_approve_for_month(self):
        self.ensure_one()

        if not self._access_approve():
            raise AccessError("Bạn không có quyền duyệt!")

        vals = {}
        discount_line_env = self.env["mv.compute.discount.line"]
        if self.quantity < self.quantity_from:
            is_two_months = False
            # |||| Case 1: For a month
            vals.update(
                {
                    "is_month": True,
                    "partner_sales_state": "qualified_by_approving",
                    "month": self.discount_line_id.month,
                    "month_money": self.amount_total
                    * self.discount_line_id.month
                    / 100,
                }
            )
            # |||| Case 2: For two months
            amount_by_two_month = 0
            previous_month = "{}/{}".format(
                str(int(self.month_parent) - 1), self.parent_id.year
            )
            discount_line_previous_month = discount_line_env.search(
                [
                    ("partner_id", "=", self.partner_id.id),
                    ("is_month", "=", True),
                    ("is_two_month", "=", False),
                    ("name", "=", previous_month),
                ]
            )
            if discount_line_previous_month:
                is_two_months = True
                for line in discount_line_previous_month:
                    amount_by_two_month += line.amount_total

                vals.update(
                    {
                        "is_two_month": True,
                        "two_month": self.discount_line_id.two_month,
                        "two_money": (amount_by_two_month + self.amount_total)
                        * self.discount_line_id.two_month
                        / 100,
                    }
                )
            self.write(vals)
            # Create history line for discount
            total_money = (
                vals["two_money"] + vals["month_money"]
                if is_two_months
                else vals["month_money"]
            )
            self.create_history_line(
                self,
                "approve_for_two_months",
                "Đã duyệt Chiết Khấu Tháng cho đại lý, đang chờ duyệt tổng tháng %s."
                % self.name,
                total_money,
            )
            # Tracking for user
            self.parent_id.message_post(
                body=Markup(
                    """
                    <div class="o_mail_notification">
                        %s đã xác nhận chiết khấu tháng cho %s. <br/>
                        Với số tiền là: <b>%s</b>
                    </div>
                """
                )
                % (
                    self.env.user.name,
                    self.partner_id.name,
                    self.format_value(
                        amount=self.month_money, currency=self.currency_id
                    ),
                )
            )

    def action_quarter(self):
        self.ensure_one()

        if not self._access_approve():
            raise AccessError("Bạn không có quyền duyệt!")

        amount_two_month = 0
        name_one = str(int(self.month_parent) - 1) + "/" + self.parent_id.year
        name_two = str(int(self.month_parent) - 2) + "/" + self.parent_id.year
        domain = [
            ("name", "in", [name_one, name_two]),
            ("partner_id", "=", self.partner_id.id),
        ]
        line_ids = self.env["mv.compute.discount.line"].search(domain)
        if len(line_ids) > 0:
            for line in line_ids:
                amount_two_month += line.amount_total
        self.write(
            {
                "is_quarter": True,
                "partner_sales_state": "qualified_by_approving",
                "quarter": self.discount_line_id.quarter,
                "quarter_money": (amount_two_month + self.amount_total)
                * self.discount_line_id.quarter
                / 100,
            }
        )
        # Create history line for discount
        total_money = (
            (amount_two_month + self.amount_total) * self.discount_line_id.quarter / 100
        )
        self.create_history_line(
            self,
            "approve_for_quarter",
            "Đã duyệt Chiết Khấu Quý cho đại lý, đang chờ duyệt tổng tháng %s."
            % self.name,
            total_money,
        )
        # Tracking for user
        self.parent_id.message_post(
            body=Markup(
                """
                <div class="o_mail_notification">
                    %s đã xác nhận chiết khấu quý cho %s. <br/>
                    Với số tiền là: <b>%s</b>
                </div>
            """
            )
            % (self.env.user.name, self.partner_id.name, str(self.quarter_money))
        )

    def action_year(self):
        self.ensure_one()

        if not self._access_approve():
            raise AccessError("Bạn không có quyền duyệt!")

        total_year = 0
        for i in range(12):
            name = str(i + 1) + "/" + self.parent_id.year
            domain = [("name", "=", name), ("partner_id", "=", self.partner_id.id)]
            line_ids = self.env["mv.compute.discount.line"].search(domain)
            if len(line_ids) > 0:
                total_year += line_ids.amount_total
        self.write(
            {
                "is_year": True,
                "partner_sales_state": "qualified_by_approving",
                "year": self.discount_line_id.year,
                "year_money": total_year * self.discount_line_id.year / 100,
            }
        )
        # Create history line for discount
        total_money = total_year * self.discount_line_id.year / 100
        self.create_history_line(
            self,
            "approve_for_quarter",
            "Đã duyệt Chiết Khấu Năm cho đại lý, đang chờ duyệt tổng tháng %s."
            % self.name,
            total_money,
        )
        # Tracking for user
        self.parent_id.message_post(
            body=Markup(
                """
                <div class="o_mail_notification">
                    %s đã xác nhận chiết khấu năm cho %s. <br/>
                    Với số tiền là: <b>%s</b>
                </div>
            """
            )
            % (self.env.user.name, self.partner_id.name, str(total_year))
        )

    def create_history_line(self, record, state, description, total_money):
        is_waiting_approval = (
            state
            in [
                "approve_for_month",
                "approve_for_two_months",
                "approve_for_quarter",
                "approve_for_year",
            ]
            and total_money > 0
        )
        return self.env["mv.discount.partner.history"]._create_history_line(
            partner_id=record.partner_id.id,
            history_description=description,
            history_date=record.parent_id.approved_date or record.write_date,
            history_user_action_id=record.write_uid.id,
            production_discount_policy_id=record.id,
            production_discount_policy_total_money=total_money,
            total_money=total_money,
            total_money_discount_display=(
                "+ {:,.2f}".format(total_money)
                if total_money > 0
                else "{:,.2f}".format(total_money)
            ),
            is_waiting_approval=is_waiting_approval,
            is_positive_money=False,
            is_negative_money=False,
        )

    # =================================
    # SQL Methods
    # =================================]

    def _sql_get_sale_promote_ids(self, partner_id, **kwargs):
        date_from = kwargs.get("date_from")
        date_to = kwargs.get("date_to")

        query = """
            SELECT so.id                                            AS sale_id,
                        SUM(sol.product_uom_qty)         AS quantity,
                        SUM(sol.qty_delivered)                AS quantity_delivered
            FROM sale_order so
                    JOIN sale_order_line AS sol ON (sol.order_id = so.id AND (sol.price_unit = 0 OR sol.discount = 100))
                    JOIN product_product AS pp ON (pp.id = sol.product_id)
                    JOIN product_template AS pt ON (pt.id = pp.product_tmpl_id AND pt.detailed_type = 'product')
            WHERE so.date_order BETWEEN %s AND %s
                AND so.partner_id = %s
                AND so.state = 'sale'
                AND (so.is_order_returns = FALSE OR so.is_order_returns ISNULL)
                AND (so.is_claim_warranty = FALSE OR so.is_claim_warranty ISNULL)
            GROUP BY so.id;
        """
        self.env.cr.execute(query, [date_from, date_to, partner_id.id])
        results = self.env.cr.fetchall()

        sales_ids = [result[0] for result in results] or []
        total_quantity_delivered = sum(result[2] for result in results) or 0

        return sales_ids, total_quantity_delivered

    def _sql_get_sale_return_ids(self, partner_id, **kwargs):
        date_from = kwargs.get("date_from")
        date_to = kwargs.get("date_to")

        query = """
            SELECT so.id                                            AS sale_id,
                        SUM(sol.product_uom_qty)         AS quantity,
                        SUM(sol.qty_delivered)                AS quantity_delivered
            FROM sale_order so
                    JOIN sale_order_line AS sol ON (sol.order_id = so.id)
                    JOIN product_product AS pp ON (pp.id = sol.product_id)
                    JOIN product_template AS pt ON (pt.id = pp.product_tmpl_id AND pt.detailed_type = 'product')
            WHERE so.date_order BETWEEN %s AND %s
                AND so.partner_id = %s
                AND so.state = 'sale'
                AND so.is_order_returns = TRUE
            GROUP BY so.id;
        """
        self.env.cr.execute(query, [date_from, date_to, partner_id.id])
        results = self.env.cr.fetchall()

        sales_ids = [result[0] for result in results] or []
        total_quantity_delivered = sum(result[2] for result in results) or 0

        return sales_ids, total_quantity_delivered

    def _sql_get_sale_claim_warranty_ids(self, partner_id, **kwargs):
        date_from = kwargs.get("date_from")
        date_to = kwargs.get("date_to")

        query = """
            SELECT so.id                                            AS sale_id,
                        SUM(sol.product_uom_qty)         AS quantity,
                        SUM(sol.qty_delivered)                AS quantity_delivered
            FROM sale_order so
                    JOIN sale_order_line AS sol ON (sol.order_id = so.id)
                    JOIN product_product AS pp ON (pp.id = sol.product_id)
                    JOIN product_template AS pt ON (pt.id = pp.product_tmpl_id AND pt.detailed_type = 'product')
            WHERE so.date_order BETWEEN %s AND %s
                AND so.partner_id = %s
                AND so.state = 'sale'
                AND so.is_claim_warranty = TRUE
            GROUP BY so.id;
        """
        self.env.cr.execute(query, [date_from, date_to, partner_id.id])
        results = self.env.cr.fetchall()

        sales_ids = [result[0] for result in results] or []
        total_quantity_delivered = sum(result[2] for result in results) or 0

        return sales_ids, total_quantity_delivered

    # =================================
    # ACTION VIEWS Methods
    # =================================

    def action_view_two_month(self):
        month = self.parent_id.month
        year = self.parent_id.year
        if month == "1":
            name_last = "12" + "/" + str(int(year) - 1)
        else:
            name_last = str(int(month) - 1) + "/" + year
        list_name = [self.name, name_last]
        domain = [("partner_id", "=", self.partner_id.id), ("name", "=", list_name)]
        line_ids = self.search(domain)
        return {
            "name": "Chiết khấu 2 tháng đạt chỉ tiêu",
            "view_mode": "tree,form",
            "res_model": "mv.compute.discount.line",
            "type": "ir.actions.act_window",
            "domain": [("id", "=", line_ids.ids)],
            "context": {
                "create": False,
                "edit": False,
                "tree_view_ref": "mv_sale.mv_compute_discount_line_tree",
                "form_view_ref": "mv_sale.mv_compute_discount_line_form",
            },
        }

    def action_view_quarter(self):
        month = self.parent_id.month
        year = self.parent_id.year
        if month == "1":
            name_last = "12" + "/" + str(int(year) - 1)
        else:
            name_last = str(int(month) - 1) + "/" + year
        name_last_last = str(int(month) - 2) + "/" + year
        list_name = [self.name, name_last, name_last_last]
        domain = [("partner_id", "=", self.partner_id.id), ("name", "=", list_name)]
        line_ids = self.search(domain)
        return {
            "name": "Chiết khấu theo quý %s đạt chỉ tiêu" % str(int(month) / 3),
            "view_mode": "tree,form",
            "res_model": "mv.compute.discount.line",
            "type": "ir.actions.act_window",
            "domain": [("id", "=", line_ids.ids)],
            "context": {
                "create": False,
                "edit": False,
                "tree_view_ref": "mv_sale.mv_compute_discount_line_tree",
                "form_view_ref": "mv_sale.mv_compute_discount_line_form",
            },
        }

    def action_view_year(self):
        year = self.parent_id.year
        list_name = [
            "1" + "/" + year,
            "2" + "/" + year,
            "3" + "/" + year,
            "4" + "/" + year,
            "5" + "/" + year,
            "6" + "7" + year,
            "8" + "/" + year,
            "9" + "/" + year,
            "10" + "/" + year,
            "11" + "/" + year,
            "12" + "/" + year,
        ]
        domain = [("partner_id", "=", self.partner_id.id), ("name", "=", list_name)]
        line_ids = self.search(domain)
        return {
            "name": "Chiết khấu theo theo năm %s" % year,
            "view_mode": "tree,form",
            "res_model": "mv.compute.discount.line",
            "type": "ir.actions.act_window",
            "domain": [("id", "=", line_ids.ids)],
            "context": {
                "create": False,
                "edit": False,
                "tree_view_ref": "mv_sale.mv_compute_discount_line_tree",
                "form_view_ref": "mv_sale.mv_compute_discount_line_form",
            },
        }

    # =================================
    # HELPER/PRIVATE Methods
    # =================================

    @api.model
    def format_value(self, amount, currency=False, blank_if_zero=False):
        """
        Format amount => monetary display (with a currency symbol).
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

    def _access_approve(self):
        """
            Helps check user security for access to Discount Line approval
        :return: True/False
        """
        return self.env.user.has_group(GROUP_APPROVER)
