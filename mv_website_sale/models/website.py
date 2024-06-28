# -*- coding: utf-8 -*-
from odoo import models, _lt


class MoveoplusWebsite(models.Model):
    _inherit = "website"

    def _get_moveoplus_checkout_step_list(self):
        """Return an ordered list of Moveo PLus steps according to the current template rendered.

            TODO: Implement the logic to add the "Moveoplus info" step when needed.

        :rtype: list
        :return: A list with the following structure:
            [
                [xmlid],
                {
                    'name': str,
                    'current_href': str,
                    'main_button': str,
                    'main_button_href': str,
                    'back_button': str,
                    'back_button_href': str
                }
            ]
        """
        self.ensure_one()
        is_extra_step_active = self.viewref("website_sale.extra_info").active
        redirect_to_sign_in = (
            self.account_on_checkout == "mandatory" and self.is_public_user()
        )

        steps = [
            (
                ["website_sale.cart"],
                {
                    "name": "Xem lại đơn hàng",
                    "current_href": "/shop/cart",
                    "main_button": (
                        "Đăng nhập" if redirect_to_sign_in else "Tiến hành thanh toán"
                    ),
                    "main_button_href": f'{"/web/login?redirect=" if redirect_to_sign_in else ""}/shop/checkout?express=1',
                    "back_button": "Tiếp tục mua hàng",
                    "back_button_href": "/shop",
                },
            ),
            (
                ["website_sale.checkout", "website_sale.address"],
                {
                    "name": "Vận chuyển",
                    "current_href": "/shop/checkout",
                    "main_button": "Xác nhận",
                    "main_button_href": f'{"/shop/extra_info" if is_extra_step_active else "/shop/confirm_order"}',
                    "back_button": "Quay lại giỏ hàng",
                    "back_button_href": "/shop/cart",
                },
            ),
        ]
        if is_extra_step_active:
            steps.append(
                (
                    ["website_sale.extra_info"],
                    {
                        "name": "Thông tin bổ sung",
                        "current_href": "/shop/extra_info",
                        "main_button": "Tiếp tục thanh toán",
                        "main_button_href": "/shop/confirm_order",
                        "back_button": "Quay lại bước vận chuyển",
                        "back_button_href": "/shop/checkout",
                    },
                )
            )
        steps.append(
            (
                ["website_sale.payment"],
                {
                    "name": "Thanh toán",
                    "current_href": "/shop/payment",
                    "back_button": "Quay lại giỏ hàng",
                    "back_button_href": "/shop/cart",
                },
            )
        )
        return steps

    def _get_checkout_steps(self, current_step=None):
        """Override of `website_sale` to add a "Moveoplus info" step when needed."""

        checkout_steps = super()._get_checkout_steps(current_step=None)
        order = self.sudo().sale_get_order()
        agency = order and order.partner_id and order.partner_id.is_agency
        if agency:
            checkout_steps = self._get_moveoplus_checkout_step_list()

        if current_step:
            return next(step for step in checkout_steps if current_step in step[0])[1]
        else:
            return checkout_steps
