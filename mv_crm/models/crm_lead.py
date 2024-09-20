from odoo import models, fields, api, _


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    company_registry = fields.Char(related='partner_id.company_registry')
    partner_survey_count = fields.Integer(string="Partner Count", compute='_compute_partner_count')

    @api.depends('partner_id')
    def _compute_partner_count(self):
        for lead in self:
            lead.partner_survey_count = self.env['mv.partner.survey'].search_count(
                [('partner_id', '=', lead.partner_id.id)])

    def redirect_mv_dms_view(self):
        self.ensure_one()
        return {
            'name': _("Partner's Surveys"),
            'view_mode': 'tree,form',
            'res_model': 'mv.partner.survey',
            'type': 'ir.actions.act_window',
            'domain': [('partner_id', '=', self.partner_id.id)],
        }
