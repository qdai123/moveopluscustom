# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    line_ids = fields.One2many("mv.discount.partner", "partner_id")
    discount_id = fields.Many2one(
        "mv.discount",
        string="Chiết khấu",
        compute="_compute_discount_id",
        store=True,
        readonly=False,
    )
    compute_discount_line_ids = fields.One2many(
        "mv.compute.discount.line", "partner_id", domain=[("parent_id", "!=", False)]
    )
    is_agency = fields.Boolean("Đại lý", copy=False)
    is_white_agency = fields.Boolean("Đại lý vùng trắng", copy=False)
    amount = fields.Integer("Tiền chiết khấu", copy=False)
    bank_guarantee = fields.Boolean("Bảo lãnh ngân hàng", copy=False)
    discount_bank_guarantee = fields.Float("Bảo lãnh ngân hàng", copy=False)
    sale_mv_ids = fields.Many2many("sale.order", compute="compute_sale_mv_ids")
    total_so_bonus_order = fields.Monetary(
        string="Tổng tiền chiết khấu",
        currency_field="currency_id",
        compute="_compute_total_amount",
        store=True,
        readonly=False,
    )
    currency_id = fields.Many2one(
        "res.currency",
        compute="_get_company_currency",
        readonly=True,
        string="Currency",
    )

    @api.onchange("is_white_agency")
    def _onchange_is_white_agency(self):
        if self.is_white_agency and not self.is_agency:
            self.is_agency = True

    @api.depends("line_ids")
    def _compute_discount_id(self):
        for record in self:
            record.discount_id = False
            line_ids = record.line_ids.filtered(lambda x: x.parent_id)
            if len(line_ids) > 0:
                record.discount_id = line_ids[0].parent_id.id

    def _get_company_currency(self):
        for partner in self:
            if partner.company_id:
                partner.currency_id = partner.sudo().company_id.currency_id
            else:
                partner.currency_id = self.env.company.currency_id

    @api.depends("sale_order_ids")
    def compute_sale_mv_ids(self):
        for record in self:
            record.sale_mv_ids = False
            if len(record.sale_order_ids) > 0:
                sale_mv_ids = record.sale_order_ids.filtered(
                    lambda x: x.bonus_order > 0 and x.state != "cancel"
                )
                record.sale_mv_ids = sale_mv_ids.ids

    @api.depends("sale_mv_ids")
    def _compute_total_amount(self):
        for record in self:
            if record.sale_mv_ids or len(record.sale_mv_ids) > 0:
                record.total_so_bonus_order = sum(
                    line.bonus_order for line in record.sale_mv_ids
                )

    @api.onchange("bank_guarantee")
    def onchange_bank_guarantee(self):
        self.discount_bank_guarantee = 0
