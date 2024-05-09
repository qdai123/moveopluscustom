# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from odoo.tools.misc import formatLang


class MvComputeDiscountLine(models.Model):
    _name = "mv.compute.discount.line"
    _description = _("Compute Discount (%) Line for Partner")
    _rec_name = "partner_id"

    name = fields.Char(related="parent_id.name", store=True)
    month_parent = fields.Integer()
    parent_id = fields.Many2one("mv.compute.discount")
    partner_id = fields.Many2one("res.partner", string="Đại lý")
    level = fields.Integer(string="Bậc")
    quantity = fields.Integer(string="Số lượng lốp đã bán")
    quantity_discount = fields.Integer(string="Số lượng khuyến mãi")
    amount_total = fields.Float(string="Doanh thu tháng")
    quantity_from = fields.Integer(string="Số lượng lốp min")
    quantity_to = fields.Integer(string="Số lượng lốp max")
    basic = fields.Float(string="Basic")
    is_month = fields.Boolean()
    month = fields.Float(string="% chiết khấu tháng")
    month_money = fields.Integer(string="Số tiền chiết khấu tháng")
    is_two_month = fields.Boolean()
    amount_two_month = fields.Float(string="Số tiền 2 Tháng")
    two_month = fields.Float(string="% chiết khấu 2 tháng")
    two_money = fields.Integer(string="Số tiền chiết khấu 2 tháng")
    is_quarter = fields.Boolean()
    quarter = fields.Float(string="% chiết khấu quý")
    quarter_money = fields.Integer(string="Số tiền chiết khấu quý")
    is_year = fields.Boolean()
    year = fields.Float(string="% chiết khấu năm")
    year_money = fields.Integer(string="Số tiền chiết khấu năm")
    total_discount = fields.Float(string="Total % discount")
    total_money = fields.Integer(
        "Tổng tiền chiết khấu ", compute="compute_total_money", store=True
    )
    sale_ids = fields.One2many("sale.order", "discount_line_id")
    order_line_ids = fields.One2many("sale.order.line", "discount_line_id")
    currency_id = fields.Many2one("res.currency", readonly=True)
    discount_line_id = fields.Many2one("mv.discount.line")

    @api.depends("month_money", "two_money", "quarter_money", "year_money")
    def compute_total_money(self):
        for record in self:
            record.total_money = (
                record.month_money
                + record.two_money
                + record.quarter_money
                + record.year_money
            )

    # =================================
    # BUSINESS Methods
    # =================================

    def action_approve_for_month(self):
        if not self._access_approve():
            raise AccessError(_("Bạn không có quyền duyệt!"))

        for rec in self:
            amount_by_month = 0
            name = "{}/{}".format(str(int(rec.month_parent)), rec.parent_id.year)
            line_ids = self.env["mv.compute.discount.line"].search(
                [
                    ("partner_id", "=", rec.partner_id.id),
                    ("name", "=", name),
                ]
            )
            if len(line_ids) > 0:
                for line in line_ids:
                    amount_by_month += line.month_money

            rec.write(
                {
                    "is_month": True,
                    "month": rec.discount_line_id.month,
                    "month_money": (amount_by_month + rec.amount_total)
                    * rec.discount_line_id.month
                    / 100,
                }
            )
            tracking_text = """
                <div class="o_mail_notification">
                    %s đã xác nhận chiết khấu tháng cho người dùng %s. <br/>
                    Với số tiền là: <b>%s</b>
                </div>
            """
            rec.parent_id.message_post(
                body=Markup(tracking_text)
                % (
                    self.env.user.name,
                    rec.partner_id.name,
                    self.format_value(amount=rec.month_money, currency=rec.currency_id),
                )
            )

    def action_quarter(self):
        if not self._access_approve():
            raise AccessError(_("Bạn không có quyền duyệt!"))

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
                "quarter": self.discount_line_id.quarter,
                "quarter_money": (amount_two_month + self.amount_total)
                * self.discount_line_id.quarter
                / 100,
            }
        )
        self.parent_id.message_post(
            body="%s đã xác nhận chiết khấu quý cho người dùng %s với số tiền là: %s"
            % (self.env.user.name, self.partner_id.name, str(self.quarter_money))
        )

    def action_year(self):
        if not self._access_approve():
            raise AccessError(_("Bạn không có quyền duyệt!"))

        total_year = 0
        for i in range(12):
            print(i)
            name = str(i + 1) + "/" + self.parent_id.year
            domain = [("name", "=", name), ("partner_id", "=", self.partner_id.id)]
            line_ids = self.env["mv.compute.discount.line"].search(domain)
            if len(line_ids) > 0:
                total_year += line_ids.amount_total
        self.write(
            {
                "is_year": True,
                "year": self.discount_line_id.year,
                "year_money": total_year * self.discount_line_id.year / 100,
            }
        )
        self.parent_id.message_post(
            body="%s đã xác nhận chiết khấu năm cho người dùng %s với số tiền là: %s"
            % (self.env.user.name, self.partner_id.name, str(total_year))
        )

    # =================================
    # ACTION VIEW Methods
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
            "name": "Chiếu khấu 2 tháng đạt chỉ tiêu",
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
            "name": "Chiếu khấu theo quý %s đạt chỉ tiêu" % str(int(month) / 3),
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
            "name": "Chiếu khấu theo theo năm %s" % (year),
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

    def _access_approve(self):
        """
            Helps check user security for access to Discount Line approval
        :return: True/False
        """

        access = self.env.user.has_group("mv_sale.group_mv_compute_discount_approver")
        return access
