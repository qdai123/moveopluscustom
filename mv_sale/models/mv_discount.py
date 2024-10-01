# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime
def year_selection():
    return [(str(year), str(year)) for year in range(2000, datetime.now().year + 1)]


class MvDiscountPolicy(models.Model):
    _name = "mv.discount"
    _description = _("MOVEO PLUS Discount Policy")

    # RELATION Fields [Many2many, One2many, Many2one]:
    partner_ids = fields.One2many(
        comodel_name="mv.discount.partner",
        inverse_name="parent_id",
        domain=[("partner_id.is_agency", "=", True)],
    )
    line_ids = fields.One2many(
        comodel_name="mv.discount.line", inverse_name="parent_id"
    )
    line_promote_ids = fields.One2many(
        comodel_name="mv.promote.discount.line", inverse_name="parent_id"
    )
    line_white_place_ids = fields.One2many(
        comodel_name="mv.white.place.discount.line", inverse_name="parent_id"
    )
    # =================================
    active = fields.Boolean(default=True)
    name = fields.Char("Chính sách chiết khấu")
    level_promote_apply = fields.Integer("Level")
    company_ids = fields.Many2many(
        'res.company',
        string='Companies',
        default=lambda self: self.env.company,
        required=True,
        groups="base.group_multi_company"
    )
    # =================================
    in_year = fields.Selection(
        selection=year_selection(),
        string='Năm (Áp dụng)',
        required=True,
        default=lambda self: str(fields.Date.today().year)
    )

    january = fields.Integer(string='Tháng 1', default=0)
    february = fields.Integer(string='Tháng 2', default=0)
    march = fields.Integer(string='Tháng 3', default=0)
    april = fields.Integer(string='Tháng 4', default=0)
    may = fields.Integer(string='Tháng 5', default=0)
    june = fields.Integer(string='Tháng 6', default=0)
    july = fields.Integer(string='Tháng 7', default=0)
    august = fields.Integer(string='Tháng 8', default=0)
    september = fields.Integer(string='Tháng 9', default=0)
    october = fields.Integer(string='Tháng 10', default=0)
    november = fields.Integer(string='Tháng 11', default=0)
    december = fields.Integer(string='Tháng 12', default=0)

    @api.depends('january', 'february', 'march')
    def _compute_first_quarter(self):
        for record in self:
            record.forecasted_sales_first_quarterly = record.january + record.february + record.march

    @api.depends('april', 'may', 'june')
    def _compute_second_quarter(self):
        for record in self:
            record.forecasted_sales_second_quarterly = record.april + record.may + record.june

    @api.depends('july', 'august', 'september')
    def _compute_third_quarter(self):
        for record in self:
            record.forecasted_sales_third_quarterly = record.july + record.august + record.september

    @api.depends('october', 'november', 'december')
    def _compute_fourth_quarter(self):
        for record in self:
            record.forecasted_sales_fourth_quarterly = record.october + record.november + record.december

    @api.depends('january', 'february', 'march', 'april', 'may', 'june',
                 'july', 'august', 'september', 'october', 'november', 'december')
    def _compute_yearly_sales(self):
        for record in self:
            record.forecasted_yearly_sales = (
                    record.january + record.february + record.march +
                    record.april + record.may + record.june +
                    record.july + record.august + record.september +
                    record.october + record.november + record.december
            )

    forecasted_sales_first_quarterly = fields.Integer(
        string='Doanh số Quý I',
        compute='_compute_first_quarter',
        readonly=True,
        store=True
    )
    forecasted_sales_second_quarterly = fields.Integer(
        string='Doanh số Quý II',
        compute='_compute_second_quarter',
        readonly=True,
        store=True
    )
    forecasted_sales_third_quarterly = fields.Integer(
        string='Doanh số Quý III',
        compute='_compute_third_quarter',
        readonly=True,
        store=True
    )
    forecasted_sales_fourth_quarterly = fields.Integer(
        string='Doanh số Quý IV',
        compute='_compute_fourth_quarter',
        readonly=True,
        store=True
    )
    forecasted_yearly_sales = fields.Integer(
        string='Số lượng tổng',
        compute='_compute_yearly_sales',
        readonly=True,
        store=True
    )

    @api.onchange('in_year')
    def _onchange_in_year(self):
        if not self.in_year:
            self.january = 0.0
            self.february = 0.0
            self.march = 0.0
            self.april = 0.0
            self.may = 0.0
            self.june = 0.0
            self.july = 0.0
            self.august = 0.0
            self.september = 0.0
            self.october = 0.0
            self.november = 0.0
            self.december = 0.0

    # =================================
    # CONSTRAINS Methods
    # =================================

    @api.constrains("line_ids", "level_promote_apply")
    def _validate_out_of_current_level(self):
        for rec in self.filtered("line_ids"):
            max_level = max(rec.line_ids.mapped("level"))
            if rec.level_promote_apply > max_level:
                raise ValidationError(
                    _("Bậc cao nhất hiện tại là %s, vui lòng nhập lại!") % max_level
                )
