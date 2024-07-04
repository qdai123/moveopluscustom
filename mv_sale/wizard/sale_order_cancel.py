# -*- coding: utf-8 -*-
from markupsafe import Markup

from odoo import fields, models


class SaleOrderCancel(models.TransientModel):
    _inherit = "sale.order.cancel"

    cancel_reason = fields.Text(string="Reason", required=True)

    def action_cancel(self):
        self.ensure_one()
        tracking_reason = '<p class="mb-0">Hủy đơn <b>%s</b></p>' % self.order_id.name
        tracking_reason += (
            """
            <ul class="o_Message_trackingValues mb-0 ps-4">
                <li>
                    <div class="o_TrackingValue d-flex align-items-center flex-wrap mb-1" role="group">
                        <span class="o_TrackingValue_Title me-1 px-1 fw-bold">Lý do: </span>
                        <span class="o_TrackingValue_Reason me-1 fw-bold text-danger">%s</span>
                    </div>
                </li>
            </ul>
        """
            % self.cancel_reason
        )
        self.order_id.message_post(body=Markup(tracking_reason))
        return super(SaleOrderCancel, self).action_cancel()
