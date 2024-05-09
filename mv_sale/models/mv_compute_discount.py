# -*- coding: utf-8 -*-
import base64
import calendar
import io
from datetime import date, datetime

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools.misc import formatLang


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
    report_date = fields.Date(compute="_compute_report_date_by_month_year", store=True)

    _sql_constraints = [
        (
            "month_year_uniq",
            "unique (month, year)",
            "Tháng và năm này đã tồn tại không được tạo nữa",
        )
    ]

    @api.depends("year", "month")
    def _compute_report_date_by_month_year(self):
        for rec in self:
            if rec.month and rec.year:
                rec.report_date = date.today().replace(
                    day=1, month=int(rec.month), year=int(rec.year)
                )
            else:
                rec.report_date = rec.create_date.date().replace(
                    day=1,
                    month=int(rec.create_date.date().month),
                    year=int(rec.create_date.date().year),
                )

    # =================================
    # BUSINESS Methods
    # =================================

    def action_reset_to_draft(self):
        self.filtered(lambda r: r.state != "draft").write({"state": "draft"})

    def action_confirm(self):
        self.line_ids = False
        list_line_ids = []
        # compute date
        date_from = "01-" + self.month + "-" + self.year
        date_from = datetime.strptime(date_from, "%d-%m-%Y")
        if self.month == "12":
            date_to = "31-" + self.month + "-" + self.year
        else:
            date_to = "01-" + str(int(self.month) + 1) + "-" + self.year
        date_to = datetime.strptime(date_to, "%d-%m-%Y")

        # domain lọc dữ liệu sale trong tháng
        domain = [
            ("date_invoice", ">=", date_from),
            ("date_invoice", "<", date_to),
            ("state", "in", ["sale"]),
        ]
        sale_ids = self.env["sale.order"].search(domain)

        # lấy tất cả đơn hàng trong tháng, có mua lốp xe có category 19
        order_line = sale_ids.order_line.filtered(
            lambda x: x.order_id.partner_id.is_agency
            and x.product_id.detailed_type == "product"
            and x.qty_delivered > 0
            and x.order_id.check_category_product(x.product_id.categ_id)
        )

        # lấy tất cả đại lý trong tháng
        partner_ids = order_line.order_id.mapped("partner_id")
        for partner_id in partner_ids:
            # giá trị ban đầu:
            discount_line_id = False
            amount_total = False
            is_month = False
            month_money = 0
            is_two_month = False
            amount_two_month = 0
            two_month = 0
            two_money = 0
            is_quarter = False
            quarter = 0
            quarter_money = 0
            is_year = False
            year = 0
            year_money = 0

            # xác định số lượng đại lý trong tháng
            order_line_total = order_line.filtered(
                lambda x: x.order_id.partner_id == partner_id
            )
            order_line_partner = order_line_total.filtered(
                lambda x: x.order_id.partner_id == partner_id and x.price_unit > 0
            )
            quantity = sum(order_line_partner.mapped("product_uom_qty"))
            # xác định số lương đơn hàng có giá = 0, hàng khuyến mãi
            order_line_partner_discount = order_line_total.filtered(
                lambda x: x.order_id.partner_id == partner_id and x.price_unit == 0
            )
            quantity_discount = sum(
                order_line_partner_discount.mapped("product_uom_qty")
            )
            # xác định cấp bậc đại lý
            line_ids = partner_id.line_ids.filtered(
                lambda x: date.today() >= x.date if x.date else not x.date
            ).sorted("level")
            if len(line_ids) > 0:
                level = line_ids[-1].level
                discount_id = line_ids[-1].parent_id
                discount_line_id = discount_id.line_ids.filtered(
                    lambda x: x.level == level
                )
                amount_total = sum(order_line_partner.mapped("price_subtotal"))
                if quantity >= discount_line_id.quantity_from:
                    # đạt được chỉ tiêu tháng 1 chỉ cần thỏa số lượng trong tháng
                    is_month = True
                    month_money = amount_total * discount_line_id.month / 100
                    # để đạt kết quả 2 tháng:
                    # 1- tháng này phải đạt chỉ tiêu tháng
                    # 2 - tháng trước phải đạt chỉ tiêu tháng và chưa đạt chỉ tiêu 2 tháng
                    if self.month == "1":
                        name = "12" + "/" + str(int(self.year) - 1)
                    else:
                        name = str(int(self.month) - 1) + "/" + self.year
                    domain = [
                        ("name", "=", name),
                        ("is_month", "=", True),
                        ("is_two_month", "=", False),
                        ("partner_id", "=", partner_id.id),
                    ]
                    line_two_month_id = self.env["mv.compute.discount.line"].search(
                        domain
                    )
                    if len(line_two_month_id) > 0:
                        is_two_month = True
                        two_month = discount_line_id.two_month
                        amount_two_month = line_two_month_id.amount_total + amount_total
                        two_money = amount_two_month * discount_line_id.two_month / 100
                    # để đạt kết quả quý [1, 2, 3] [4, 5, 6] [7, 8, 9] [10, 11, 12]:
                    # chỉ xét quý vào các tháng 3 6 9 12, chỉ cần kiểm tra 2 tháng trước đó có đạt chỉ tiêu tháng ko
                    if self.month in ["3", "6", "9", "12"]:
                        name_one = str(int(self.month) - 1) + "/" + self.year
                        name_two = str(int(self.month) - 2) + "/" + self.year
                        domainone = [
                            ("name", "=", name_one),
                            ("is_month", "=", True),
                            ("partner_id", "=", partner_id.id),
                        ]
                        line_name_one = self.env["mv.compute.discount.line"].search(
                            domainone
                        )
                        domain_two = [
                            ("name", "=", name_two),
                            ("is_month", "=", True),
                            ("partner_id", "=", partner_id.id),
                        ]
                        line_name_two = self.env["mv.compute.discount.line"].search(
                            domain_two
                        )
                        if len(line_name_one) >= 1 and len(line_name_two) >= 1:
                            is_quarter = True
                            quarter = discount_line_id.quarter
                            quarter_money = (
                                (
                                    amount_total
                                    + line_name_one.amount_total
                                    + line_name_two.amount_total
                                )
                                * discount_line_id.two_month
                                / 100
                            )
                    # để đạt kết quả năm thì tháng đang xet phai la 12
                    # kiểm tra 11 tháng trước đó đã được chỉ tiêu tháng chưa
                    if self.month in ["12"]:
                        flag = True
                        total_year = 0
                        for i in range(12):
                            name = str(i + 1) + "/" + self.year
                            domain = [
                                ("name", "=", name),
                                ("is_month", "=", True),
                                ("partner_id", "=", partner_id.id),
                            ]
                            line_name = self.env["mv.compute.discount.line"].search(
                                domain
                            )
                            if len(line_name) == 0:
                                flag = False
                            total_year += line_name.amount_total
                        if flag:
                            is_year = True
                            year = discount_line_id.quarter
                            year_money = total_year * discount_line_id.year / 100

            if discount_line_id.level:
                value = (
                    0,
                    0,
                    {
                        # tính dữ liệu tháng này
                        "discount_line_id": discount_line_id.id,
                        "month_parent": int(self.month),
                        "partner_id": partner_id.id,
                        "level": discount_line_id.level,
                        "sale_ids": order_line_total.order_id.ids,
                        "order_line_ids": order_line_total.ids,
                        "currency_id": order_line_total[0].order_id.currency_id.id,
                        "quantity": quantity,
                        "quantity_discount": quantity_discount,
                        "quantity_from": discount_line_id.quantity_from,
                        "quantity_to": discount_line_id.quantity_to,
                        "amount_total": amount_total,
                        "is_month": is_month,
                        "month": discount_line_id.month,
                        "month_money": month_money,
                        # tính 2 tháng
                        "is_two_month": is_two_month,
                        "amount_two_month": amount_two_month,
                        "two_month": two_month,
                        "two_money": two_money,
                        # tính theo quý
                        "is_quarter": is_quarter,
                        "quarter": quarter,
                        "quarter_money": quarter_money,
                        # tính theo năm
                        "is_year": is_year,
                        "year": year,
                        "year_money": year_money,
                    },
                )
                list_line_ids.append(value)
        self.write(
            {
                "line_ids": list_line_ids,
                "state": "confirm",
            }
        )

    def action_done(self):
        if not self._access_approve():
            raise AccessError(_("Bạn không có quyền duyệt!"))

        for rec in self:
            if rec.line_ids:
                for discount_line in self.line_ids:
                    discount_line.partner_id.write(
                        {
                            "amount": discount_line.partner_id.amount
                            + discount_line.total_money
                        }
                    )
            rec.write({"state": "done"})

    def action_undo(self):
        self.write(
            {
                "state": "draft",
                "line_ids": False,
            }
        )

    def action_view_tree(self):
        return {
            "name": "Kết quả chiết khấu của tháng: %s" % self.name,
            "view_mode": "tree,form",
            "res_model": "mv.compute.discount.line",
            "type": "ir.actions.act_window",
            "domain": [("parent_id", "=", self.id)],
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

    def _access_approve(self):
        """
            Helps check user security for access to Discount Line approval
        :return: True/False
        """

        access = self.env.user.has_group("mv_sale.group_mv_compute_discount_approver")
        return access

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
                SELECT ROW_NUMBER() OVER ()  AS row_index,
                           partner.name          AS sub_dealer,
                           cdl.level             AS level,
                           cdl.quantity_from     AS quantity_from,
                           cdl.quantity          AS quantity,
                           cdl.quantity_discount AS quantity_discount,
                           cdl.amount_total      AS total,
                           cdl.month_money       AS month_money,
                           cdl.two_money         AS two_money,
                           cdl.quarter_money     AS quarter_money,
                           cdl.year_money        AS year_money,
                           cdl.total_money       AS total_money
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
        sheet = workbook.add_worksheet(
            "Discount in {}-{}".format(self.report_date.month, self.report_date.year)
        )
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
        sheet.merge_range("A1:L1", "", DEFAULT_FORMAT)
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
        sheet.write("E2", "Số lượng lốp đã bán (Cái)", SUB_TITLE_FORMAT)

        # ////// NAME = "Số lượng lốp Khuyến Mãi (Cái)"
        sheet.merge_range("F2:F3", "", DEFAULT_FORMAT)
        sheet.write("F2", "Số lượng lốp Khuyến Mãi (Cái)", SUB_TITLE_FORMAT)

        # ////// NAME = "Doanh thu Tháng"
        sheet.merge_range("G2:G3", "", DEFAULT_FORMAT)
        sheet.write("G2", "Doanh thu Tháng", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu tháng"
        sheet.merge_range("H2:H3", "", DEFAULT_FORMAT)
        sheet.write("H2", "Số tiền chiết khấu tháng", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu 2 tháng"
        sheet.merge_range("I2:I3", "", DEFAULT_FORMAT)
        sheet.write("I2", "Số tiền chiết khấu 2 tháng", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu quý"
        sheet.merge_range("J2:J3", "", DEFAULT_FORMAT)
        sheet.write("J2", "Số tiền chiết khấu quý", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Số tiền chiết khấu năm"
        sheet.merge_range("K2:K3", "", DEFAULT_FORMAT)
        sheet.write("K2", "Số tiền chiết khấu năm", SUB_TITLE_TOTAL_FORMAT)

        # ////// NAME = "Tổng tiền chiết khấu"
        sheet.merge_range("L2:L3", "", DEFAULT_FORMAT)
        sheet.write("L2", "Tổng tiền chiết khấu", SUB_TITLE_TOTAL_FORMAT)

        sheet.set_column(4, 11, 15)

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
                    if col in [6, 7, 8, 9, 10, 11]:
                        sheet.write(count, col, data[key], BODY_TOTAL_NUM_FORMAT)
                    else:
                        sheet.write(count, col, data[key], BODY_NUM_FORMAT)
                else:
                    sheet.write(count, col, data[key])

        # ############# [FOOTER] ###########################################

        workbook.close()
        output.seek(0)

        return output.read(), file_name.replace("-", "_")
