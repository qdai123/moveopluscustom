# -*- coding: utf-8 -*-
from odoo import fields, models


def get_years():
    year_list = []
    for i in range(2023, 2036):
        year_list.append((str(i), str(i)))
    return year_list


class MvReportDiscount(models.TransientModel):
    _name = "mv.report.discount"
    _description = "Màn hình báo cáo"

    year = fields.Selection(get_years(), string="Chọn Năm", required=1)
    partner_id = fields.Many2one("res.partner")
    type = fields.Selection(
        [
            ("1", "Chiết khấu 2 tháng"),
            ("2", "Chiết khấu theo quý"),
            ("3", "Chiết khấu theo năm"),
        ]
    )
    value_month = fields.Selection(
        [
            ("1", "Tháng 12 năm trước và 1 năm nay"),
            ("2", "Tháng 1 và 2"),
            ("3", "Tháng 2 và 3"),
            ("4", "Tháng 3 và 4"),
            ("5", "Tháng 4 và 5"),
            ("6", "Tháng 5 và 6"),
            ("7", "Tháng 6 và 7"),
            ("8", "Tháng 7 và 8"),
            ("9", "Tháng 8 và 9"),
            ("10", "Tháng 9 và 10"),
            ("11", "Tháng 10 và 11"),
            ("12", "Tháng 11 và 12"),
        ],
        string="Tháng",
    )
    value_quarter = fields.Selection(
        [("3", "Quý 1"), ("6", "Quý 2"), ("9", "Quý 3"), ("12", "Quý 4")], string="Quý"
    )

    def button_confirm(self):
        if self.type == "1":
            return self.action_view_two_month()
        elif self.type == "2":
            return self.action_view_quarter()
        else:
            return self.action_view_year()

    def action_view_two_month(self):
        month = self.value_month
        year = self.year
        name = month + "/" + year
        line_ids = self.env["mv.compute.discount.line"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("is_two_month", "=", True),
                ("name", "=", name),
            ]
        )
        if len(line_ids) == 0:
            return {
                "name": "Tổng đơn " + self.value_month,
                "view_mode": "tree,form",
                "res_model": "sale.order",
                "type": "ir.actions.act_window",
                "domain": [("id", "in", line_ids.sale_ids.ids)],
                "context": {
                    "create": False,
                    "edit": False,
                },
            }
        if month == "1":
            name_last = "12" + "/" + str(int(year) - 1)
        else:
            name_last = str(int(month) - 1) + "/" + year
        list_name = [name, name_last]
        domain = [("partner_id", "=", self.partner_id.id), ("name", "=", list_name)]
        line_ids = self.env["mv.compute.discount.line"].search(domain)
        return {
            "name": "Tổng đơn " + self.value_month,
            "view_mode": "tree,form",
            "res_model": "sale.order",
            "type": "ir.actions.act_window",
            "domain": [("id", "in", line_ids.sale_ids.ids)],
            "context": {
                "create": False,
                "edit": False,
            },
        }

    def action_view_quarter(self):
        month = self.value_quarter
        year = self.year
        name = month + "/" + year
        line_ids = self.env["mv.compute.discount.line"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("is_quarter", "=", True),
                ("name", "=", name),
            ]
        )
        if len(line_ids) == 0:
            return {
                "name": "Tổng đơn " + self.value_quarter,
                "view_mode": "tree,form",
                "res_model": "sale.order",
                "type": "ir.actions.act_window",
                "domain": [("id", "in", line_ids.sale_ids.ids)],
                "context": {
                    "create": False,
                    "edit": False,
                },
            }
        if month == "1":
            name_last = "12" + "/" + str(int(year) - 1)
        else:
            name_last = str(int(month) - 1) + "/" + year
        name_last_last = str(int(month) - 2) + "/" + year
        list_name = [name, name_last, name_last_last]
        domain = [("partner_id", "=", self.partner_id.id), ("name", "in", list_name)]
        line_ids = self.env["mv.compute.discount.line"].search(domain)
        return {
            "name": "Tổng đơn " + self.value_quarter,
            "view_mode": "tree,form",
            "res_model": "sale.order",
            "type": "ir.actions.act_window",
            "domain": [("id", "in", line_ids.sale_ids.ids)],
            "context": {
                "create": False,
                "edit": False,
            },
        }

    def action_view_year(self):
        year = self.year
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
        line_ids = self.env["mv.compute.discount.line"].search(
            [
                ("partner_id", "=", self.partner_id.id),
                ("is_year", "=", True),
                ("name", "=", "12" + "/" + year),
            ]
        )
        if len(line_ids) == 0:
            return {
                "name": "Tổng đơn " + self.year,
                "view_mode": "tree,form",
                "res_model": "sale.order",
                "type": "ir.actions.act_window",
                "domain": [("id", "in", line_ids.sale_ids.ids)],
                "context": {
                    "create": False,
                    "edit": False,
                },
            }
        domain = [("partner_id", "=", self.partner_id.id), ("name", "=", list_name)]
        line_ids = self.env["mv.compute.discount.line"].search(domain)
        return {
            "name": "Tổng đơn năm" + self.year,
            "view_mode": "tree,form",
            "res_model": "sale.order",
            "type": "ir.actions.act_window",
            "domain": [("id", "in", line_ids.sale_ids.ids)],
            "context": {
                "create": False,
                "edit": False,
            },
        }
