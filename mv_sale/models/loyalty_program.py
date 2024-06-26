# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class LoyaltyProgram(models.Model):
    _inherit = "loyalty.program"

    apply_for = fields.Boolean(string="Apply for", default=False)
    partner_agency_ok = fields.Boolean(string="Partner Agency")
    partner_white_agency_ok = fields.Boolean(string="Partner White Agency")
    partner_southern_agency_ok = fields.Boolean(string="Partner Southern Agency")

    @api.constrains(
        "partner_agency_ok", "partner_white_agency_ok", "partner_southern_agency_ok"
    )
    def _validate_only_one_partner_agency(self):
        for program in self:
            true_fields_count = sum(
                [
                    program.partner_agency_ok,
                    program.partner_white_agency_ok,
                    program.partner_southern_agency_ok,
                ]
            )
            if true_fields_count > 1:
                raise ValidationError(
                    "Bạn không thể chọn nhiều hơn một loại Đại lý cho chương trình khuyến mãi này."
                )
