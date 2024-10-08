# -*- coding: utf-8 -*-
from odoo import models


class MoveoplusWebsite(models.Model):
    _inherit = "website"

    # === MOVEOPLUS OVERRIDE ===#

    def _get_button_details(self, redirect_to_sign_in, is_checkout_step):
        """Helper function to get main and back button details."""
        if is_checkout_step:
            main_button = "Xác nhận"
            main_button_href = (
                "/shop/extra_info"
                if self.viewref("website_sale.extra_info").active
                else "/shop/confirm_order"
            )
            back_button = "Quay lại giỏ hàng"
            back_button_href = "/shop/cart"
        else:
            main_button = "Đăng nhập" if redirect_to_sign_in else "Tiến hành thanh toán"
            main_button_href = f'{"/web/login?redirect=" if redirect_to_sign_in else ""}/shop/checkout?express=1'
            back_button = "Tiếp tục mua hàng"
            back_button_href = "/shop"

        return main_button, main_button_href, back_button, back_button_href

    def _generate_step(
        self,
        xmlid,
        name,
        current_href,
        main_button,
        main_button_href,
        back_button,
        back_button_href,
    ):
        """Helper function to generate a step."""
        return (
            [xmlid],
            {
                "name": name,
                "current_href": current_href,
                "main_button": main_button,
                "main_button_href": main_button_href,
                "back_button": back_button,
                "back_button_href": back_button_href,
            },
        )

    def _get_moveoplus_checkout_agency_step_list(self):
        """Return an ordered list of Moveo PLus steps according to the current template rendered."""
        self.ensure_one()
        is_extra_step_active = self.viewref("website_sale.extra_info").active
        redirect_to_sign_in = (
            self.account_on_checkout == "mandatory" and self.is_public_user()
        )

        steps = [
            self._generate_step(
                "website_sale.cart",
                "Xem lại đơn hàng",
                "/shop/cart",
                *self._get_button_details(redirect_to_sign_in, is_checkout_step=False),
            ),
            self._generate_step(
                ["website_sale.checkout", "website_sale.address"],
                "Vận chuyển",
                "/shop/checkout",
                *self._get_button_details(
                    redirect_to_sign_in=False, is_checkout_step=True
                ),
            ),
        ]

        if is_extra_step_active:
            steps.append(
                self._generate_step(
                    "website_sale.extra_info",
                    "Thông tin bổ sung",
                    "/shop/extra_info",
                    "Tiếp tục thanh toán",
                    "/shop/confirm_order",
                    "Quay lại bước vận chuyển",
                    "/shop/checkout",
                )
            )

        steps.append(
            self._generate_step(
                "website_sale.payment",
                "Thanh toán",
                "/shop/payment",
                "",
                "",
                "Quay lại giỏ hàng",
                "/shop/cart",
            )
        )
        return steps

    def _get_checkout_steps(self, current_step=None):
        """Override of `website_sale` to add a "Moveoplus for Partner Agency" step when needed."""
        checkout_steps = super()._get_checkout_steps(current_step)
        order = self.sudo().sale_get_order()
        agency = order and order.partner_id and order.partner_id.is_agency

        if agency:
            checkout_steps = self._get_moveoplus_checkout_agency_step_list()

        if current_step:
            return next(step for step in checkout_steps if current_step in step[0])[1]

        return checkout_steps
