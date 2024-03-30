# -*- coding: utf-8 -*-

from odoo import models, api, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    line_ids = fields.One2many("mv.discount.partner", "partner_id")
    discount_id = fields.Many2one("mv.discount", compute="compute_discount_id", store=True, readonly=False)
    amount = fields.Integer("Tiền chiết khấu", copy=False)
    is_agency = fields.Boolean(string="Đại lý", copy=False)
    bank_guarantee = fields.Boolean(string="Bảo lãnh ngân hàng", copy=False)
    discount_bank_guarantee = fields.Float(string="Bảo lãnh ngân hàng", copy=False)
    compute_discount_line_ids = fields.One2many("mv.compute.discount.line", "partner_id")
    sale_mv_ids = fields.Many2many('sale.order', compute="compute_sale_mv_ids")

    @api.depends("sale_order_ids")
    def compute_sale_mv_ids(self):
        for record in self:
            record.sale_mv_ids = False
            if len(record.sale_order_ids) > 0:
                sale_mv_ids = record.sale_order_ids.filtered(lambda x: x.bonus_order > 0 and x.state != 'cancel')
                record.sale_mv_ids = sale_mv_ids.ids

    @api.depends("line_ids")
    def compute_discount_id(self):
        for record in self:
            record.discount_id = False
            line_ids = record.line_ids.filtered(lambda x: x.parent_id)
            if len(line_ids) > 0:
                record.discount_id = line_ids[0].parent_id.id

    @api.onchange("bank_guarantee")
    def onchange_bank_guarantee(self):
        self.discount_bank_guarantee = 0
