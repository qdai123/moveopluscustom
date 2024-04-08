# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        context = dict(self.env.context or {})
        sales_manager = self.env.user.has_group("sales_team.group_sale_manager")
        check_domain_access_on_sales_groups = context.get("check_domain_access_on_sales_groups", False)
        if check_domain_access_on_sales_groups and not sales_manager:
            args = ["&", ["detailed_type", "!=", "service"]] + args
        return super(ProductTemplate, self).name_search(name, args, operator=operator, limit=limit)

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        context = dict(self.env.context or {})
        sales_manager = self.env.user.has_group("sales_team.group_sale_manager")
        check_domain_access_on_sales_groups = context.get("check_domain_access_on_sales_groups", False)
        if check_domain_access_on_sales_groups and not sales_manager:
            domain = ["&", ["detailed_type", "!=", "service"]] + domain

        return super(ProductTemplate, self).web_search_read(
            domain, specification, offset=offset, limit=limit, order=order, count_limit=limit
        )
