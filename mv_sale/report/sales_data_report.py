# -*- coding: utf-8 -*-
import logging

from odoo.addons.mv_sale.models.sale_order import (
    GROUP_SALESPERSON,
    GROUP_SALES_ALL,
    GROUP_SALES_MANAGER,
)
from odoo.addons.sale.models.sale_order import SALE_ORDER_STATE

from odoo import _, api, fields, models, tools
from odoo.osv import expression

_logger = logging.getLogger(__name__)


class SalesDataReport(models.Model):
    _name = "sales.data.report"
    _description = _("Sales Data Analysis Report")
    _auto = False
    _rec_name = "sale_date_order"
    _order = "sale_date_order, sale_week_number"

    @api.model
    def _get_done_states(self):
        return ["sale"]

    # [sale.order] fields
    sale_id = fields.Many2one(
        "sale.order",
        "Order",
        readonly=True,
        index=True,
    )
    sale_reference = fields.Char(
        "Order Reference",
        readonly=True,
        index=True,
    )
    sale_date_order = fields.Date("Order Date", readonly=True)
    sale_weekday_order = fields.Char("Weekday (Order)", readonly=True)
    sale_week_number = fields.Char("Week Number (Order)", readonly=True)
    sale_week_name = fields.Char("Week (Order)", readonly=True)
    sale_year_order = fields.Char("Year (Order)", readonly=True)
    sale_month_order = fields.Char("Month (Order)", readonly=True)
    sale_day_order = fields.Char("Day (Order)", readonly=True)
    sale_date_invoice = fields.Date("Order Date Invoiced", readonly=True)
    sale_year_invoice = fields.Char("Year (Invoice)", readonly=True)
    sale_month_invoice = fields.Char("Month (Invoice)", readonly=True)
    sale_day_invoice = fields.Char("Day (Invoice)", readonly=True)
    sale_partner_id = fields.Many2one(
        "res.partner",
        "Customer",
        readonly=True,
        index=True,
    )
    sale_company_id = fields.Many2one("res.company", "Company", readonly=True)
    sale_pricelist_id = fields.Many2one("product.pricelist", "Pricelist", readonly=True)
    sale_team_id = fields.Many2one(
        "crm.team",
        "Sales Team",
        readonly=True,
        index=True,
    )
    sale_user_id = fields.Many2one(
        "res.users",
        "Salesperson",
        readonly=True,
        index=True,
    )
    sale_status = fields.Selection(SALE_ORDER_STATE, "Status", readonly=True)
    sale_analytic_account_id = fields.Many2one(
        "account.analytic.account", "Analytic Account", readonly=True
    )
    sale_invoice_status = fields.Selection(
        [
            ("upselling", "Upselling Opportunity"),
            ("invoiced", "Fully Invoiced"),
            ("to invoice", "To Invoice"),
            ("no", "Nothing to Invoice"),
        ],
        "Invoice Status",
        readonly=True,
    )

    # [res.partner] fields
    partner_nickname = fields.Char("Nickname", readonly=True)
    company_registry = fields.Char("Company ID", readonly=True)
    commercial_partner_id = fields.Many2one(
        "res.partner",
        "Customer Entity",
        readonly=True,
    )
    country_id = fields.Many2one(
        "res.country",
        "Customer Country",
        readonly=True,
    )
    state_id = fields.Many2one(
        "res.country.state",
        "Customer Region",
        readonly=True,
    )
    district_id = fields.Many2one(
        "res.country.district",
        "Customer District",
        readonly=True,
    )
    wards_id = fields.Many2one(
        "res.country.wards",
        "Customer Ward",
        readonly=True,
    )
    street = fields.Char("Customer Street", readonly=True)
    delivery_address = fields.Char(
        "Customer Delivery Address",
        compute="_compute_delivery_address",
    )

    # [sale.order.line] fields
    order_reference = fields.Reference(
        string="Related Order",
        selection=[("sale.order", "Sales Order")],
        group_operator="count_distinct",
    )
    product_category_id = fields.Many2one(
        "product.category",
        "Product Category",
        readonly=True,
    )
    product_id = fields.Many2one(
        "product.product",
        "Product Variant",
        readonly=True,
    )
    product_template_id = fields.Many2one(
        "product.template",
        "Product",
        readonly=True,
    )
    product_country_of_origin = fields.Many2one(
        "res.country",
        "Origin of goods",
        readonly=True,
    )
    product_att_size_lop = fields.Char("Size", readonly=True)
    product_att_dong_lop = fields.Char("Tire line", readonly=True)
    product_att_ma_gai = fields.Char("Thorny Code", readonly=True)
    product_att_rim_diameter_inch = fields.Char("Rim", readonly=True)
    product_uom = fields.Many2one("uom.uom", "Unit of Measure", readonly=True)
    product_uom_qty = fields.Float("Qty Ordered", readonly=True)
    qty_delivered = fields.Float("Qty Delivered", readonly=True)
    qty_invoiced = fields.Float("Qty Invoiced", readonly=True)
    price_unit = fields.Float("Price Unit", readonly=True)
    price_subtotal = fields.Monetary("Untaxed Total", readonly=True)
    price_total = fields.Monetary("Total", readonly=True)
    discount = fields.Float("Discount %", readonly=True, group_operator="avg")
    discount_amount = fields.Monetary("Discount Amount", readonly=True)

    # [stock.lot] fields
    serial_number = fields.Char("Serial Number", readonly=True)
    qrcode = fields.Char("Qr-Code", readonly=True)

    # aggregates or computed fields
    currency_id = fields.Many2one("res.currency", compute="_compute_currency_id")

    def _fields_ignored_to_search(self):
        return [
            "order_reference",
            "sale_year_order",
            "sale_month_order",
            "sale_day_order",
            "sale_year_invoice",
            "sale_month_invoice",
            "sale_day_invoice",
            "currency_id",
            "discount_amount",
            "price_subtotal",
            "price_total",
            "product_uom",
            "delivery_address",
            "commercial_partner_id",
            "sale_pricelist_id",
            "sale_analytic_account_id",
        ]

    @api.model
    def fields_get(self, allfields=None, attributes=None):
        fields_get = super(SalesDataReport, self).fields_get(
            allfields=allfields, attributes=attributes
        )

        for field in self._fields_ignored_to_search():
            fields_get.get(field, {}).setdefault("searchable", True)
            fields_get[field]["searchable"] = False
            fields_get[field]["group_expand"] = None

        return fields_get

    @api.depends_context("allowed_company_ids")
    def _compute_currency_id(self):
        self.currency_id = self.env.company.currency_id

    @api.depends("sale_id", "sale_id.partner_shipping_id")
    def _compute_delivery_address(self):
        sale_orders = self.mapped("sale_id").sudo()
        shipping_partners = sale_orders.mapped("partner_shipping_id")
        shipping_addresses = {
            partner.id: partner.full_address_vi for partner in shipping_partners
        }

        for record in self:
            order = record.sale_id
            if order and order.partner_shipping_id:
                record.delivery_address = shipping_addresses.get(
                    order.partner_shipping_id.id, ""
                )

    # ==================================
    # SQL Queries / Initialization
    # ==================================

    def _select_partners(self):
        query = """
            SELECT p.id,
                        p_ship.id               AS partner_shipping_id,
                        p.short_name            AS partner_nickname,
                        p.company_registry      AS company_registry,
                        p.commercial_partner_id AS commercial_partner_id,
                        p_ship.street           AS street,
                        p_ship.wards_id         AS wards_id,
                        p_ship.district_id      AS district_id,
                        p_ship.state_id         AS state_id,
                        p_ship.country_id       AS country_id
            FROM res_partner p
                    JOIN res_partner p_ship ON p_ship.parent_id = p.id
            WHERE p.active 
                    AND p.is_agency
                    AND EXISTS (SELECT 1
                            FROM sale_order s
                            WHERE s.partner_id = p.id AND s.id != 0)
                    AND p_ship.type = 'delivery'
                    AND p_ship.wards_id IS NOT NULL
                    AND p_ship.district_id IS NOT NULL
                    AND p_ship.state_id IS NOT NULL
                    AND p_ship.country_id IS NOT NULL
        """
        return query

    def _select_products(self):
        query = """
            SELECT p.id                 AS product_id,
                        t.id                 AS product_template_id,
                        pav.name ->> 'en_US' AS attribute_name,
                        patt.attribute_code
            FROM product_product p
                JOIN product_template t ON t.id = p.product_tmpl_id
                JOIN product_template_attribute_line taline ON taline.product_tmpl_id = t.id
                JOIN product_attribute patt ON patt.id = taline.attribute_id
                JOIN product_template_attribute_value ptav 
                        ON ptav.product_tmpl_id = t.id AND ptav.attribute_id = patt.id
                JOIN product_attribute_value pav ON pav.id = ptav.product_attribute_value_id
            WHERE p.active AND t.sale_ok AND t.detailed_type = 'product'
        """
        return query

    def _select_filtered_attributes(self):
        context = dict(self.env.context or {})
        size_lop = context.get("att_size_lop", "size_lop")
        dong_lop = context.get("att_dong_lop", "dong_lop")
        ma_gai = context.get("att_ma_gai", "ma_gai")
        rim_diameter_inch = context.get("att_rim_diameter_inch", "rim_diameter_inch")

        query = f"""
            SELECT product_id,
                        product_template_id,
                        MAX(attribute_name)
                        FILTER (WHERE attribute_code IN ('{size_lop}', '{size_lop}_duplicated'))                   AS attribute_1,
                        MAX(attribute_name)
                        FILTER (WHERE attribute_code IN ('{ma_gai}', '{ma_gai}_duplicated'))                       AS attribute_2,
                        MAX(attribute_name)
                        FILTER (WHERE attribute_code IN ('{rim_diameter_inch}', '{rim_diameter_inch}_duplicated')) AS attribute_3,
                        MAX(attribute_name)
                        FILTER (WHERE attribute_code IN ('{dong_lop}', '{dong_lop}_duplicated'))                   AS attribute_4
            FROM products
            GROUP BY product_id, product_template_id
        """
        return query

    def select_orders(self):
        select_ = f"""
            SELECT l.product_id                     AS product_id,
                        t.uom_id                          AS product_uom,
                       CASE
                           WHEN l.product_id IS NOT NULL AND SUM(l.product_uom_qty) > 0
                               THEN 1.0
                           ELSE 0 END                   AS product_uom_qty,
                       CASE
                           WHEN l.product_id IS NOT NULL AND SUM(l.qty_delivered) > 0
                               THEN 1.0
                           ELSE 0 END                   AS qty_delivered,
                       CASE
                           WHEN l.product_id IS NOT NULL AND SUM(l.qty_invoiced) > 0
                               THEN 1.0
                           ELSE 0 END                   AS qty_invoiced,
                       l.price_unit                     AS price_unit,
                       CASE
                           WHEN l.product_id IS NOT NULL AND SUM(l.product_uom_qty) > 0
                               THEN ((l.price_total_before_discount / l.product_uom_qty) -
                                     ((l.price_total_before_discount / l.product_uom_qty) * l.discount / 100))
                                        / {self._case_value_or_one('s.currency_rate')}
                                   * {self._case_value_or_one('currency_table.rate')}
                           ELSE 0
                           END                          AS price_subtotal,
                       CASE
                           WHEN l.product_id IS NOT NULL AND SUM(l.product_uom_qty) > 0
                               THEN (l.price_total / l.product_uom_qty)
                                         / {self._case_value_or_one('s.currency_rate')}
                                   * {self._case_value_or_one('currency_table.rate')}
                           ELSE 0
                           END                          AS price_total,
                       s.id                               AS sale_id,
                       l.id                               AS sale_order_line_id,
                       s.name                             AS sale_reference,
                       s.date_order                       AS sale_date_order,
                       EXTRACT(DAY FROM s.date_order)     AS sale_day_order,
                       EXTRACT(MONTH FROM s.date_order)   AS sale_month_order,
                       EXTRACT(YEAR FROM s.date_order)    AS sale_year_order,
                       ((EXTRACT(DOW FROM s.date_order) - 1) % 7 + 1) AS sale_weekday_order,
                       CEIL(EXTRACT(DAY FROM (DATE_TRUNC('week', s.date_order) + INTERVAL '6 days')::DATE) /
                            7.0)                                      AS sale_week_number,
                       'Week ' ||
                       CEIL(EXTRACT(DAY FROM (DATE_TRUNC('week', s.date_order) + INTERVAL '6 days')::DATE) /
                            7.0)                                      AS sale_week_name,
                       s.date_invoice                     AS sale_date_invoice,
                       EXTRACT(DAY FROM s.date_invoice)   AS sale_day_invoice,
                       EXTRACT(MONTH FROM s.date_invoice) AS sale_month_invoice,
                       EXTRACT(YEAR FROM s.date_invoice)  AS sale_year_invoice,
                       s.state                            AS sale_status,
                       s.invoice_status                   AS sale_invoice_status,
                       s.partner_id                       AS sale_partner_id,
                       s.user_id                          AS sale_user_id,
                       s.company_id                       AS sale_company_id,
                       t.categ_id                         AS product_category_id,
                       s.pricelist_id                     AS sale_pricelist_id,
                       s.analytic_account_id              AS sale_analytic_account_id,
                       s.team_id                          AS sale_team_id,
                       p.product_tmpl_id                  AS product_template_id,
                       t.country_of_origin                AS product_country_of_origin,
                       l.discount                         AS discount,
                       CASE
                           WHEN l.product_id IS NOT NULL AND SUM(l.product_uom_qty) > 0 THEN
                               (l.price_unit * 1.0 * l.discount / 100.0)
                                   / {self._case_value_or_one('s.currency_rate')}
                                   * {self._case_value_or_one('currency_table.rate')}
                           ELSE 0
                           END                          AS discount_amount,
                       CONCAT('sale.order', ',', s.id)  AS order_reference,
                       partner.partner_nickname,
                       partner.company_registry,
                       partner.commercial_partner_id,
                       partner.street,
                       partner.wards_id,
                       partner.district_id,
                       partner.state_id,
                       partner.country_id,
                       patt.attribute_1,
                       patt.attribute_2,
                       patt.attribute_3,
                       patt.attribute_4
        """

        additional_fields_info = self._select_additional_fields()
        template = """,
                    %s AS %s"""
        for fname, query_info in additional_fields_info.items():
            select_ += template % (query_info, fname)

        return select_

    def _case_value_or_one(self, value):
        return f"""CASE COALESCE({value}, 0) WHEN 0 THEN 1.0 ELSE {value} END"""

    def _select_additional_fields(self):
        """Hook to return additional fields SQL specification for select part of the table query.

        :returns: mapping field -> SQL computation of field, will be converted to '_ AS _field' in the final table definition
        :rtype: dict
        """
        return {}

    def from_orders(self):
        return """
            FROM sale_order_line l
                LEFT JOIN sale_order s ON s.id = l.order_id
                JOIN partners partner 
                        ON partner.id = s.partner_id AND partner.partner_shipping_id = s.partner_shipping_id
                LEFT JOIN product_product p ON l.product_id = p.id
                LEFT JOIN product_template t ON p.product_tmpl_id = t.id AND t.detailed_type = 'product'
                JOIN filtered_attributes patt ON patt.product_id = l.product_id
                LEFT JOIN uom_uom u ON u.id = l.product_uom
                LEFT JOIN uom_uom u2 ON u2.id = t.uom_id
                JOIN {currency_table} ON currency_table.company_id = s.company_id
                """.format(
            currency_table=self.env["res.currency"]._get_query_currency_table(
                self.env.companies.ids, fields.Date.today()
            )
        )

    def where_orders(self):
        return """
            WHERE l.display_type IS NULL
                  AND l.is_service IS DISTINCT FROM TRUE
                  AND s.state = 'sale'
                  AND s.is_order_returns IS DISTINCT FROM TRUE
        """

    def groupby_orders(self):
        return """
            GROUP BY l.product_id,
                             t.uom_id,
                             s.id,
                             l.id,
                             s.name,
                             CONCAT('sale.order', ',', s.id),
                             s.date_order,
                             EXTRACT(DAY FROM s.date_order),
                             EXTRACT(MONTH FROM s.date_order),
                             EXTRACT(YEAR FROM s.date_order),
                             sale_weekday_order,
                             sale_week_number,
                             sale_week_name,
                             s.date_invoice,
                             EXTRACT(DAY FROM s.date_invoice),
                             EXTRACT(MONTH FROM s.date_invoice),
                             EXTRACT(YEAR FROM s.date_invoice),
                             s.state,
                             s.invoice_status,
                             s.partner_id,
                             s.user_id,
                             s.company_id,
                             t.categ_id,
                             s.pricelist_id,
                             s.analytic_account_id,
                             s.team_id,
                             p.product_tmpl_id,
                             t.country_of_origin,
                             partner.company_registry,
                             partner.commercial_partner_id,
                             partner.partner_nickname,
                             partner.company_registry,
                             partner.commercial_partner_id,
                             partner.street,
                             partner.wards_id,
                             partner.district_id,
                             partner.state_id,
                             partner.country_id,
                             patt.attribute_1,
                             patt.attribute_2,
                             patt.attribute_3,
                             patt.attribute_4,
                             l.discount,
                             l.price_unit,
                             l.product_uom_qty,
                             l.price_total,
                             l.price_subtotal,
                             currency_table.rate
        """

    def _select_orders(self):
        select_ = self.select_orders()
        from_ = self.from_orders()
        where_ = self.where_orders()
        groupby_ = self.groupby_orders()

        query = f"""
            {select_}
            {from_}
            {where_}
            {groupby_}
        """
        return query

    def _with_clause(self):
        query = f"""
            partners AS (%s),
            products AS (%s),
            filtered_attributes AS (%s),
            orders AS (%s)
        """ % (
            self._select_partners(),
            self._select_products(),
            self._select_filtered_attributes(),
            self._select_orders(),
        )
        return query

    def _select_clause(self):
        return """
            SELECT ROW_NUMBER() OVER () AS id,
                        sml.product_id,
                        lot.name             AS serial_number,
                        lot.ref              AS qrcode,
                        so.product_uom,
                        so.product_uom_qty,
                        so.qty_delivered,
                        so.qty_invoiced,
                        so.price_unit,
                        so.price_total,
                        so.price_subtotal,
                        so.sale_id,
                        so.sale_reference,
                        so.order_reference,
                        so.sale_date_order,
                        so.sale_day_order,
                        so.sale_month_order,
                        so.sale_year_order,
                        so.sale_weekday_order,
                        so.sale_week_number,
                        so.sale_week_name,
                        so.sale_status,
                        so.sale_date_invoice,
                        so.sale_day_invoice,
                        so.sale_month_invoice,
                        so.sale_year_invoice,
                        so.sale_invoice_status,
                        so.sale_user_id,
                        so.sale_partner_id,
                        so.sale_company_id,
                        so.product_category_id,
                        so.sale_pricelist_id,
                        so.sale_analytic_account_id,
                        so.sale_team_id,
                        so.product_template_id,
                        so.product_country_of_origin,
                        so.attribute_1       AS product_att_size_lop,
                        so.attribute_2       AS product_att_ma_gai,
                        so.attribute_3       AS product_att_rim_diameter_inch,
                        so.attribute_4       AS product_att_dong_lop,
                        so.discount,
                        so.discount_amount,
                        so.company_registry,
                        so.commercial_partner_id,
                        so.partner_nickname,
                        so.street,
                        so.wards_id,
                        so.district_id,
                        so.state_id,
                        so.country_id
        """

    def _from_clause(self):
        return """
            FROM stock_move_line sml
                JOIN stock_lot lot ON lot.id = sml.lot_id
                JOIN stock_move sm ON sm.id = sml.move_id
                JOIN orders so 
                        ON so.sale_order_line_id = sm.sale_line_id 
                            AND so.product_id = sm.product_id
                JOIN stock_picking picking_out
                        ON picking_out.id = sml.picking_id 
                            AND picking_out.state = 'done' 
                            AND picking_out.return_id ISNULL
        """

    def _where_clause(self):
        return """
            WHERE lot.name NOT IN (SELECT DISTINCT lot.name
                                                    FROM stock_move_line move_line
                                                            JOIN stock_lot lot ON lot.id = move_line.lot_id
                                                            JOIN stock_picking picking_in 
                                                                ON picking_in.id = move_line.picking_id
                                                    WHERE picking_in.state = 'done'
                                                        AND picking_in.return_id = picking_out.id)
        """

    def _group_by_clause(self):
        return ""

    def query(self):
        return f"""
              WITH 
              {self._with_clause()}
              {self._select_clause()}
              {self._from_clause()}
              {self._where_clause()}
              {self._group_by_clause()}
        """

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s);" % (self._table, self.query())
        )

    @api.model
    def get_views(self, views, options=None):
        res = super(SalesDataReport, self).get_views(views, options)
        if (
            self.env.user.has_group(GROUP_SALESPERSON)
            and not self.env.user.has_group(GROUP_SALES_ALL)
            and not self.env.user.has_group(GROUP_SALES_MANAGER)
        ):
            action_view = self.env.ref(
                "mv_sale.sales_data_report_action_view_salesman_only"
            )
            if options:
                options["action_id"] = action_view.id

            res["models"]["sales.data.report"]["sale_user_id"].update(
                {"domain": [("id", "=", self.env.user.id)]}
            )
        return res

    @api.model
    def web_search_read(
        self, domain, specification, offset=0, limit=None, order=None, count_limit=None
    ):
        if (
            self.env.user.has_group(GROUP_SALESPERSON)
            and not self.env.user.has_group(GROUP_SALES_ALL)
            and not self.env.user.has_group(GROUP_SALES_MANAGER)
        ):
            domain = expression.AND([domain, [("sale_user_id", "=", self.env.user.id)]])

        has_orders_today = self.env["sale.order"].search_count(
            [
                ("state", "=", "sale"),
                ("date_order", "=", fields.Date.today()),
            ]
        )
        if has_orders_today > 0:
            _logger.debug("SalespersonReport: Orders found today.")
            self.init()

        # Ensure the order parameter is not empty or improperly formatted
        if not order:
            order = "sale_date_order DESC, sale_reference DESC"

        return super(SalesDataReport, self).web_search_read(
            domain,
            specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )

    @api.model
    def web_read_group(
        self, domain, fields, groupby, limit=None, offset=0, orderby=False, lazy=True
    ):
        if (
            self.env.user.has_group(GROUP_SALESPERSON)
            and not self.env.user.has_group(GROUP_SALES_ALL)
            and not self.env.user.has_group(GROUP_SALES_MANAGER)
        ):
            domain = expression.AND([domain, [("sale_user_id", "=", self.env.user.id)]])

        sales = super(SalesDataReport, self).web_read_group(
            domain,
            fields,
            groupby,
            limit=limit,
            offset=offset,
            orderby=orderby,
            lazy=lazy,
        )

        # Check if 'product_template_id' is in groupby and 'price_unit' is in fields
        if "product_id" in groupby and "price_unit" in fields:
            # Iterate over the result groups
            for line in sales["groups"]:
                # Adjust 'price_unit' by dividing it by the count of 'product_template_id'
                line["price_unit"] = line["price_unit"] / line["product_id_count"]

        return sales
