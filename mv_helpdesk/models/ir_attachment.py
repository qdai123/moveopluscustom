from odoo import models, api, exceptions, _

class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    @api.model
    def check(self, mode, values=None):
        if mode == 'unlink' and self.ids:
            # Search for attachments related to helpdesk tickets
            attachments = self.search([('id', 'in', self.ids), ('res_model', '=', 'helpdesk.ticket')])
            if attachments:
                # Check user permissions
                if self.env.user.has_group('base.group_user') and not self.env.user.has_group('helpdesk.group_helpdesk_manager'):
                    raise exceptions.AccessError(_("You are not allowed to delete attachments of helpdesk tickets."))
        return super(IrAttachment, self).check(mode, values)
