# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import fields, models


class SaleOrderCancel(models.TransientModel):
    _inherit = "sale.order.cancel"

    cancel_reason = fields.Text(string="Reason", required=True)

    def action_cancel(self):
        tracking_reason = """
            <div class="o_mail_notification">
                %s đã hủy đơn với lý do:\n- <b>%s</b>
            </div>
        """
        self.order_id.message_post(
            body=Markup(tracking_reason) % (self.author_id.name, self.cancel_reason)
        )
        return super(SaleOrderCancel, self).action_cancel()
