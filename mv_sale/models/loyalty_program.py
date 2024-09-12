# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class LoyaltyProgram(models.Model):
    _name = "loyalty.program"
    _inherit = ["loyalty.program", "mail.thread", "mail.activity.mixin"]
    def write(self, vals):
        result = super(LoyaltyProgram, self).write(vals)
        for record in self:
            record.message_post(
                body=f'Record updated by {self.env.user.name}',
                subject='Record Updated',
                message_type='notification',
                subtype_id=self.env.ref('mail.mt_note').id
            )
        return result


    apply_for = fields.Boolean(string="Apply for", default=False)
    apply_for_all_agency = fields.Boolean(string="All")
    partner_agency_ok = fields.Boolean(string="Partner Agency")
    partner_white_agency_ok = fields.Boolean(string="Partner White Agency")
    partner_southern_agency_ok = fields.Boolean(string="Partner Southern Agency")

    @api.constrains(
        "apply_for_all_agency",
        "partner_agency_ok",
        "partner_white_agency_ok",
        "partner_southern_agency_ok",
    )
    def _validate_only_one_partner_agency(self):
        for program in self:
            true_fields_count = sum(
                [
                    program.apply_for_all_agency,
                    program.partner_agency_ok,
                    program.partner_white_agency_ok,
                    program.partner_southern_agency_ok,
                ]
            )
            if true_fields_count > 1:
                raise ValidationError(
                    "Bạn không thể chọn nhiều hơn một loại Đại lý cho chương trình khuyến mãi này "
                    "hoặc có thể chọn Tất cả"
                )
