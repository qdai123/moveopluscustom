# -*- coding: utf-8 -*-
import logging

from odoo.addons.mv_sale.models.sale_order import (
    GROUP_SALESPERSON,
    GROUP_SALES_ALL,
    GROUP_SALES_MANAGER,
)
from odoo.addons.sale.models.sale_order import SALE_ORDER_STATE

from odoo import _, api, fields, models, tools

_logger = logging.getLogger(__name__)


class SalesDataReport(models.Model):
    _name = "sales.data.report"
    _description = _("Sales Data Analysis Report")
    _auto = False
    _rec_name = "sale_date_order"
    _order = "sale_date_order DESC, serial_number"

    @api.model
    def _get_done_states(self):
        return ["sale"]

    # [sale.order] fields
    sale_id = fields.Many2one("sale.order", "Order ID", readonly=True)
    sale_reference = fields.Char("Order Reference", readonly=True)
    sale_date_order = fields.Date("Order Date", readonly=True)
    sale_year_order = fields.Char("Year", readonly=True)
    sale_month_order = fields.Char("Month", readonly=True)
    sale_day_order = fields.Char("Day", readonly=True)
    sale_partner_id = fields.Many2one("res.partner", "Customer", readonly=True)
    sale_company_id = fields.Many2one("res.company", "Company", readonly=True)
    sale_pricelist_id = fields.Many2one("product.pricelist", "Pricelist", readonly=True)
    sale_team_id = fields.Many2one("crm.team", "Sales Team", readonly=True)
    sale_user_id = fields.Many2one("res.users", "Salesperson", readonly=True)
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
    company_registry = fields.Char("Company ID", readonly=True)
    commercial_partner_id = fields.Many2one(
        "res.partner",
        "Customer Entity",
        readonly=True,
    )
    industry_id = fields.Many2one(
        "res.partner.industry",
        "Customer Industry",
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
    product_att_ma_gai = fields.Char("Thorny Code", readonly=True)
    product_att_rim_diameter_inch = fields.Char("Rim", readonly=True)
    product_promotion = fields.Boolean("Is promo?", readonly=True)
    product_uom = fields.Many2one(
        "uom.uom",
        "Unit of Measure",
        readonly=True,
    )
    product_uom_qty = fields.Float("Qty Ordered", readonly=True)
    qty_to_deliver = fields.Float("Qty To Deliver", readonly=True)
    qty_delivered = fields.Float("Qty Delivered", readonly=True)
    qty_to_invoice = fields.Float("Qty To Invoice", readonly=True)
    qty_invoiced = fields.Float("Qty Invoiced", readonly=True)
    price_unit = fields.Float("Price Unit", eadonly=True)
    price_subtotal = fields.Monetary("Untaxed Total", readonly=True)
    price_total = fields.Monetary("Total", readonly=True)
    untaxed_amount_to_invoice = fields.Monetary(
        "Untaxed Amount To Invoice", readonly=True
    )
    untaxed_amount_invoiced = fields.Monetary("Untaxed Amount Invoiced", readonly=True)
    weight = fields.Float("Gross Weight", readonly=True)
    volume = fields.Float("Volume", readonly=True)
    discount = fields.Float("Discount %", readonly=True, group_operator="avg")
    discount_amount = fields.Monetary("Discount Amount", readonly=True)

    # [stock.lot] fields
    serial_number = fields.Char("Serial Number", readonly=True)
    qrcode = fields.Char("Qr-Code", readonly=True)

    # aggregates or computed fields
    nbr = fields.Integer("# of Lines", readonly=True)
    currency_id = fields.Many2one("res.currency", compute="_compute_currency_id")

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

    def _with_clause(self):
        is_salesman = self.env.user.has_group(GROUP_SALESPERSON)
        is_sales_all = self.env.user.has_group(GROUP_SALES_ALL)
        is_sales_manager = self.env.user.has_group(GROUP_SALES_MANAGER)

        context = dict(self.env.context or {})
        size_lop = context.get("att_size_lop", "size_lop")
        ma_gai = context.get("att_ma_gai", "ma_gai")
        rim_diameter_inch = context.get("att_rim_diameter_inch", "rim_diameter_inch")

        # [>] Query "Orders" and "Order Lines"
        if not is_sales_all and not is_sales_manager and is_salesman:
            and_CLAUSE = f"AND so.user_id = {self.env.user.id}"
        else:
            and_CLAUSE = ""

        filtered_sale_order = """
            SELECT so.id,
                        so.user_id,
                        so.date_order::DATE,
                        EXTRACT(DAY FROM so.date_order)             AS sale_day_order,
                        EXTRACT(MONTH FROM so.date_order)       AS sale_month_order,
                        EXTRACT(YEAR FROM so.date_order)            AS sale_year_order,
                        so.partner_id,
                        so.partner_shipping_id
            FROM sale_order so
            WHERE so.state = 'sale'
                AND so.is_order_returns IS DISTINCT FROM TRUE
                {and_CLAUSE}
        """.format(
            and_CLAUSE=and_CLAUSE
        )
        orders = """
            SELECT fso.id                       AS sale_id,
                       fso.user_id                  AS sale_user_id,
                       fso.date_order               AS sale_date_order,
                       fso.sale_day_order,
                       fso.sale_month_order,
                       fso.sale_year_order,
                       partner.id                   AS partner_id,
                       partner.company_registry     AS company_registry,
                       partner_shipping.street      AS street,
                       partner_shipping.wards_id    AS wards_id,
                       partner_shipping.district_id AS district_id,
                       partner_shipping.state_id    AS state_id,
                       partner_shipping.country_id  AS country_id,
                       picking.id                   AS stock_picking_id,
                       sm.id                        AS stock_move_id
                FROM filtered_sale_order fso
                         INNER JOIN res_partner partner ON fso.partner_id = partner.id AND partner.is_agency = TRUE
                         INNER JOIN res_partner partner_shipping ON fso.partner_shipping_id = partner_shipping.id
                         JOIN stock_picking AS picking ON picking.sale_id = fso.id
                         JOIN stock_picking_type AS picking_type ON picking.picking_type_id = picking_type.id
                         JOIN stock_move AS sm ON sm.picking_id = picking.id
                WHERE picking.state = 'done' AND picking_type.code = 'outgoing'
        """
        order_lines = """
            SELECT sol.order_id AS order_id,
                        so.stock_picking_id,
                        so.stock_move_id
            FROM sale_order_line sol
                    JOIN orders AS so ON so.sale_id = sol.order_id
                    JOIN product_product AS pp ON pp.id = sol.product_id
                    JOIN product_template AS pt ON pt.id = pp.product_tmpl_id
            WHERE sol.state = 'sale'
                AND pt.detailed_type = 'product'
                AND sol.is_service IS DISTINCT FROM TRUE
            GROUP BY sol.order_id, so.stock_picking_id, so.stock_move_id
        """

        # [>] Query "Stock Move Lines"
        move_lines = """
            SELECT sml.id,
                        sol.order_id,
                        sml.picking_id,
                        sml.product_id,
                        stl.name AS lot_serial_number,
                        stl.ref  AS qr_code
            FROM stock_move_line sml
                JOIN stock_lot AS stl ON stl.id = sml.lot_id
                JOIN order_lines AS sol ON sol.stock_move_id = sml.move_id AND sol.stock_picking_id = sml.picking_id
        """

        # [>] Query "Product Attributes"
        product_atts = f"""
            SELECT pp.id                                      AS product_id,
                        MAX(CASE
                               WHEN paatt.attribute_code IN ('{size_lop}', '{size_lop}_duplicated')
                                   THEN pav.name ->> 'en_US' END) AS product_att_size_lop,
                        MAX(CASE
                               WHEN paatt.attribute_code IN ('{ma_gai}', '{ma_gai}_duplicated')
                                   THEN pav.name ->> 'en_US' END) AS product_att_ma_gai,
                        MAX(CASE
                               WHEN paatt.attribute_code IN
                                    ('{rim_diameter_inch}', '{rim_diameter_inch}_duplicated')
                                   THEN pav.name ->> 'en_US' END) AS product_att_rim_diameter_inch
            FROM product_product pp
                JOIN product_template pt 
                        ON pt.id = pp.product_tmpl_id
                JOIN product_template_attribute_line ptal 
                        ON ptal.product_tmpl_id = pt.id
                JOIN product_attribute paatt 
                        ON paatt.id = ptal.attribute_id
                JOIN product_template_attribute_value ptav 
                        ON ptav.product_tmpl_id = pt.id AND ptav.attribute_id = paatt.id
                JOIN product_attribute_value pav 
                        ON pav.id = ptav.product_attribute_value_id
            WHERE pp.id IN (SELECT product_id FROM stock_move_lines)
            GROUP BY pp.id
        """

        result = f"""
            filtered_sale_order AS (%s),
            orders AS (%s),
            order_lines AS (%s),
            stock_move_lines AS (%s),
            product_attributes AS (%s)
        """ % (
            filtered_sale_order,
            orders,
            order_lines,
            move_lines,
            product_atts,
        )
        return result

    def _select_product_attributes(self):
        """
        Get the product attributes to be selected in the Query
        All attributes use for this report:
            - Size (size_lop)
            - Thorny Code (ma_gai)
            - Rim Diameter (rim_diameter_inch)
            - Tire Line (dong_lop)
        """
        context = dict(self.env.context or {})
        size_lop = context.get("att_size_lop", "size_lop")
        dong_lop = context.get("att_dong_lop", "dong_lop")
        ma_gai = context.get("att_ma_gai", "ma_gai")
        rim_diameter_inch = context.get("att_rim_diameter_inch", "rim_diameter_inch")

        query = f"""
            SELECT p.id                                                             AS product_id,
                        MAX(CASE
                            WHEN patt.attribute_code IN ('{size_lop}', '{size_lop}_duplicated')
                                THEN patt.name ->> 'en_US' END)     AS attribute_1,
                       MAX(CASE
                               WHEN patt.attribute_code IN ('{ma_gai}', '{ma_gai}_duplicated')
                                   THEN pav.name ->> 'en_US' END)   AS attribute_2,
                       MAX(CASE
                               WHEN patt.attribute_code IN
                                    ('{rim_diameter_inch}', '{rim_diameter_inch}_duplicated')
                                   THEN pav.name ->> 'en_US' END)   AS attribute_3,
                       MAX(CASE
                              WHEN patt.attribute_code IN
                                    ('{dong_lop}', '{dong_lop}_duplicated')
                                    THEN pav.name ->> 'en_US' END) AS attribute_4
            FROM product_product p
                    JOIN product_template t ON t.id = p.product_tmpl_id
                    JOIN product_template_attribute_line taline ON taline.product_tmpl_id = t.id
                    JOIN product_attribute patt ON patt.id = taline.attribute_id
                    JOIN product_template_attribute_value ptav 
                            ON ptav.product_tmpl_id = t.id AND ptav.attribute_id = patt.id
                    JOIN product_attribute_value pav ON pav.id = ptav.product_attribute_value_id
            WHERE p.active AND t.sale_ok
            GROUP BY p.id
        """
        return query

    def _select_clause(self):
        return """
            SELECT ROW_NUMBER() OVER ()   AS id,
                        line.product_id        AS product_id,
                        sol.price_unit         AS price_unit,
                        pt.country_of_origin   AS product_country_of_origin,
                        pt.categ_id            AS product_category_id,
                        so.sale_id,
                        so.sale_user_id,
                        so.sale_date_order,
                        so.sale_day_order,
                        so.sale_month_order,
                        so.sale_year_order,
                        so.partner_id,
                        so.company_registry,
                        so.street,
                        so.wards_id,
                        so.district_id,
                        so.state_id,
                        so.country_id,
                        line.lot_serial_number AS serial_number,
                        line.qr_code           AS qrcode,
                        pa.product_att_size_lop,
                        pa.product_att_ma_gai,
                        pa.product_att_rim_diameter_inch
        """

    def _case_value_or_one(self, value):
        return f"""CASE COALESCE({value}, 0) WHEN 0 THEN 1.0 ELSE {value} END"""

    def _select_additional_fields(self):
        """Hook to return additional fields SQL specification for select part of the table query.

        :returns: mapping field -> SQL computation of field, will be converted to '_ AS _field' in the final table definition
        :rtype: dict
        """
        return {}

    def _from_clause(self):
        return """
            FROM stock_move_lines line
                LEFT JOIN orders AS so ON so.sale_id = line.order_id
                LEFT JOIN sale_order_line AS sol ON sol.order_id = line.order_id AND sol.product_id = line.product_id
                JOIN product_attributes pa ON pa.product_id = line.product_id
                JOIN product_product pp ON pp.id = line.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
        """

    def _where_clause(self):
        return ""

    def _group_by_clause(self):
        return """
            GROUP BY line.product_id, sol.price_unit, pt.country_of_origin, pt.categ_id, so.sale_id, so.sale_user_id,
                so.sale_date_order, so.sale_day_order, so.sale_month_order, so.sale_year_order, so.partner_id,
                so.company_registry, so.street, so.wards_id, so.district_id, so.state_id, so.country_id,
                line.lot_serial_number, line.qr_code, pa.product_att_size_lop, pa.product_att_ma_gai,
                pa.product_att_rim_diameter_inch
        """

    def query(self):
        with_ = self._with_clause()
        return f"""
            {"WITH" + with_ + "(" if with_ else ""}
            SELECT {self._select_clause()}
            FROM {self._from_clause()}
            WHERE {self._where_clause()}
            GROUP BY {self._group_by_clause()}
            {")" if with_ else ""}
        """

    @property
    def _table_query(self):
        return self._query()

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s);" % (self._table, self.query())
        )

    @api.model
    def web_search_read(
        self, domain, specification, offset=0, limit=None, order=None, count_limit=None
    ):
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
            order = "sale_date_order DESC, serial_number"

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
