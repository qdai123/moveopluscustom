# -*- coding: utf-8 -*-
from odoo import models


class Http(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        res = super(Http, self).session_info()

        # MOVEO PLUS Override to update Expiration Date

        ICP = self.env['ir.config_parameter'].sudo()
        User = self.env.user

        if User._is_internal() or User.has_group('base.group_user'):
            res['warning'] = False
            res['expiration_date'] = ICP.set_param(
                'database.expiration_date',
                "2100-12-31 23:00:00"
            )
            res['expiration_reason'] = ICP.set_param(
                'database.expiration_reason',
                "moveoplus"
            )

        return res
