# -*- coding: utf-8 -*-
import logging

from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.sale.controllers import portal

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MoveoplusCustomerPortal(portal.CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        partner_discount_history = request.env["mv.discount.partner.history"]
        if "history_count" in counters:
            values["history_count"] = (
                partner_discount_history.search_count(
                    self._prepare_discount_history_domain(partner), limit=1
                )
                if partner_discount_history.check_access_rights(
                    "read", raise_exception=False
                )
                else 0
            )

        return values

    def _prepare_discount_history_domain(self, partner):
        return [("partner_id", "child_of", [partner.commercial_partner_id.id])]

    def _get_discount_history_searchbar_sortings(self):
        return {
            "date": {"label": "Ngày ghi nhận", "data": "create_date desc"},
        }

    def _prepare_discount_history_portal_values(
        self, page=1, date_begin=None, date_end=None, sortby=None, **kwargs
    ):
        _logger.info(f"kwargs: {kwargs}")
        partner_discount_history = request.env["mv.discount.partner.history"]

        if not sortby:
            sortby = "date"

        partner = request.env.user.partner_id
        values = self._prepare_portal_layout_values()

        url = "/my/discount_histories"
        domain = self._prepare_discount_history_domain(partner)

        searchbar_sortings = self._get_discount_history_searchbar_sortings()
        sort_data = searchbar_sortings[sortby]["data"]

        if date_begin and date_end:
            domain += [
                ("create_date", ">", date_begin),
                ("create_date", "<=", date_end),
            ]

        pager_values = portal_pager(
            url=url,
            total=partner_discount_history.search_count(domain),
            page=page,
            step=self._items_per_page,
            url_args={"date_begin": date_begin, "date_end": date_end, "sortby": sortby},
        )
        records_history = partner_discount_history.search(
            domain,
            order=sort_data,
            limit=self._items_per_page,
            offset=pager_values["offset"],
        )

        values.update(
            {
                "date": date_begin,
                "histories": (
                    records_history.sudo()
                    if records_history
                    else partner_discount_history
                ),
                "page_name": "discount_history",
                "pager": pager_values,
                "default_url": url,
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
            }
        )

        return values

    @http.route(
        ["/my/discount_histories", "/my/discount_histories/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_discount_history(self, **kwargs):
        values = self._prepare_discount_history_portal_values(**kwargs)
        request.session["my_partner_discount_history"] = values["histories"].ids[:100]
        return request.render("mv_sale.portal_my_discount_history", values)
