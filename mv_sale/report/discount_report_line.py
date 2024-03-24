# -*- coding: utf-8 -*-

from odoo import models, api, fields


class DiscountReportLine(models.Model):
    _name = 'discount.report.line'

    parent_id = fields.Many2one("discount.report")
    partner_id = fields.Many2one("res.partner", related="parent_id.partner_id")
    description = fields.Char(string=" ")
    january = fields.Char(string="Tháng 1")
    february = fields.Char(string="Tháng 2")
    march = fields.Char(string="Tháng 3")
    april = fields.Char(string="Tháng 4")
    may = fields.Char(string="Tháng 5")
    june = fields.Char(string="Tháng 6")
    july = fields.Char(string="Tháng 7")
    august = fields.Char(string="Tháng 8")
    september = fields.Char(string="Tháng 9")
    october = fields.Char(string="Tháng 10")
    november = fields.Char(string="Tháng 11")
    december = fields.Char(string="Tháng 12")
