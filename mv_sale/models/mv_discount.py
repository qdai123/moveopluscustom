# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


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
