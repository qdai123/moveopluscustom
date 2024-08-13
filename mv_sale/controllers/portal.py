# -*- coding: utf-8 -*-
import logging

from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.sale.controllers import portal

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class MoveoplusCustomerPortal(portal.CustomerPortal):

    def _get_history_data_count(self, partner):
        count = 0

        partner_discount_history = request.env["mv.discount.partner.history"]
        domain = self._prepare_discount_history_domain(partner)
        count += partner_discount_history.search_count(domain)

        partner_total_discount_detail_history = request.env[
            "mv.partner.total.discount.detail.history"
        ]
        count += partner_total_discount_detail_history.search_count(
            domain=[("partner_id", "child_of", [partner.commercial_partner_id.id])]
        )

        return count

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        partner = request.env.user.partner_id

        if "history_count" in counters:
            if (
                request.env["mv.discount.partner.history"]
                .sudo()
                .check_access_rights("read", raise_exception=False)
            ):
                values["history_count"] = self._get_history_data_count(partner)
            else:
                values["history_count"] = 0

        return values

    def _prepare_discount_history_domain(self, partner):
        return [
            "&",
            ("partner_id", "child_of", [partner.commercial_partner_id.id]),
            "|",
            "|",
            "&",
            ("sale_order_id", "!=", False),
            ("is_negative_money", "=", True),
            "&",
            ("production_discount_policy_id", "!=", False),
            ("is_positive_money", "=", True),
            "&",
            ("warranty_discount_policy_id", "!=", False),
            ("is_positive_money", "=", True),
        ]

    def _get_discount_history_searchbar_sortings(self):
        return {
            "date": {"label": "Ngày ghi nhận", "data": "history_date desc"},
        }

    def _prepare_discount_history_portal_values(
        self, page=1, date_begin=None, date_end=None, sortby=None, **kwargs
    ):
        _logger.info(f"kwargs: {kwargs}")

        keys_list = []
        result_histories = []
        result_histories_ordered = []
        partner_discount_history = request.env["mv.discount.partner.history"]
        partner_total_discount_detail_history = request.env[
            "mv.partner.total.discount.detail.history"
        ]

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
                ("history_date", ">", date_begin),
                ("history_date", "<=", date_end),
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
        for history in records_history:
            if not history.production_discount_policy_id:
                keys_list.append(
                    f"{history.history_date.month}_{history.history_date.year}"
                )
                result_histories.append(
                    {
                        f"{history.history_date.month}_{history.history_date.year}": {
                            "history_date": history.history_date,
                            "history_description": history.history_description,
                            "total_discount_amount": history.total_money,
                            "total_money_discount_display": history.total_money_discount_display,
                            "is_positive_money": history.is_positive_money,
                            "is_negative_money": history.is_negative_money,
                        }
                    }
                )

        records_total_discount_detail_history = (
            partner_total_discount_detail_history.search(
                domain=[("partner_id", "child_of", [partner.commercial_partner_id.id])],
                order=sort_data,
                limit=self._items_per_page,
                offset=pager_values["offset"],
            )
        )
        if records_total_discount_detail_history:
            for history_detail in records_total_discount_detail_history:
                keys_list.append(
                    f"{history_detail.history_date.month}_{history_detail.history_date.year}"
                )
                result_histories.append(
                    {
                        f"{history_detail.history_date.month}_{history_detail.history_date.year}": {
                            "history_date": history_detail.history_date,
                            "history_description": history_detail.description,
                            "total_discount_amount": history_detail.total_discount_amount,
                            "total_money_discount_display": history_detail.total_discount_amount_display,
                            "is_positive_money": True,
                            "is_negative_money": False,
                        }
                    }
                )

        keys_list = sorted(list(set(keys_list)), reverse=True)
        result_histories = sorted(
            result_histories, key=lambda r: r.keys(), reverse=True
        )
        if keys_list and result_histories:
            for key in keys_list:
                for data in result_histories:
                    if key in data:
                        data = data[key]
                        result_histories_ordered.append(data)

        values.update(
            {
                "date": date_begin,
                "partner_name": partner.short_name,
                "histories": (
                    records_history.sudo()
                    if records_history
                    else partner_discount_history
                ),
                "histories_total_detail": (
                    records_total_discount_detail_history.sudo()
                    if records_total_discount_detail_history
                    else partner_total_discount_detail_history
                ),
                "result_histories": result_histories_ordered,
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
