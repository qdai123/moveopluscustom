from odoo import models, fields, api, _


class CrmLead(models.Model):
    _inherit = 'crm.lead'
    _description = 'MV CRM Lead'

    company_registry = fields.Char(related='partner_id.company_registry', string='Customer ID')
    partner_count = fields.Integer(string="Partner Count", compute='_compute_partner_count')

    @api.depends('partner_id')
    def _compute_partner_count(self):
        for lead in self:
            partner_records = self.env['mv.partner.survey'].search([('partner_id', '=', lead.partner_id.id)])
            lead.partner_count = len(partner_records)

    def redirect_mv_dms_view(self):
        self.ensure_one()
        return {
            'name': _('DMS Files'),
            'view_mode': 'tree',
            'res_model': 'mv.partner.survey',
            'type': 'ir.actions.act_window',
            'domain': [('partner_id', '=', self.partner_id.id)],
        }
