# -*- coding: utf-8 -*-
import logging

from odoo.addons.mv_sale.models.sale_order import (
    GROUP_SALESPERSON,
    GROUP_SALES_ALL,
    GROUP_SALES_MANAGER,
)

from odoo import _, api, fields, models, tools

_logger = logging.getLogger(__name__)


class SalespersonReport(models.Model):
    _name = "salesperson.report"
    _description = _("Salesperson's Analysis Report")
    _auto = False
    _rec_name = "product_template_id"
    _rec_names_search = ["sale_id", "partner_id", "serial_number", "qrcode"]
    _order = "sale_date_order DESC, sale_id DESC"

    # ==== Product/Product template FIELDS ==== #
    product_category_id = fields.Many2one("product.category", readonly=True)
    product_id = fields.Many2one("product.product", readonly=True)
    product_price_unit = fields.Float(digits="Product Price", readonly=True)
    product_country_of_origin = fields.Many2one("res.country", readonly=True)
    product_att_size_lop = fields.Char(readonly=True)
    product_att_ma_gai = fields.Char(readonly=True)
    product_att_rim_diameter_inch = fields.Char(readonly=True)
    product_template_id = fields.Many2one(
        "product.template", compute="_compute_product"
    )
    product_price_subtotal = fields.Float(
        digits="Product Price", compute="_compute_product_total"
    )
    product_promotion = fields.Boolean(compute="_compute_product_total")
    # ==== Stock FIELDS ==== #
    serial_number = fields.Char(readonly=True)
    qrcode = fields.Char(readonly=True)
    # ==== Sale FIELDS ==== #
    sale_id = fields.Many2one("sale.order", readonly=True)
    sale_user_id = fields.Many2one("res.users", readonly=True)
    sale_date_order = fields.Date(readonly=True)
    sale_day_order = fields.Char(readonly=True)
    sale_month_order = fields.Char(readonly=True)
    sale_year_order = fields.Char(readonly=True)
    # ==== Partner FIELDS ==== #
    partner_id = fields.Many2one("res.partner", readonly=True)
    partner_company_registry = fields.Char(readonly=True)
    street = fields.Char(readonly=True)
    wards_id = fields.Many2one("res.country.wards", readonly=True)
    district_id = fields.Many2one("res.country.district", readonly=True)
    state_id = fields.Many2one("res.country.state", readonly=True)
    country_id = fields.Many2one("res.country", readonly=True)
    delivery_address = fields.Char(compute="_compute_sale_id")

    @api.depends("sale_id", "sale_id.partner_shipping_id")
    def _compute_sale_id(self):
        for record in self:
            order = record.sale_id.sudo()
            if order and order.partner_shipping_id:
                record.delivery_address = order.partner_shipping_id.full_address_vi

    @api.depends("product_id")
    def _compute_product(self):
        for record in self:
            record.product_template_id = record.product_id.product_tmpl_id

    @api.depends("sale_id", "product_id")
    def _compute_product_total(self):
        for record in self:
            # Filter order lines within the sale order, avoiding unnecessary searches
            product_order_lines = record.sale_id.order_line.filtered(
                lambda line: line.product_id == record.product_id
            )

            if product_order_lines:
                for product_line in product_order_lines:
                    # If the price subtotal is positive, calculate the discounted price
                    record.product_price_subtotal = max(
                        0,
                        product_line.price_unit * (1 - product_line.discount / 100),
                    )
                    record.product_promotion = False
            else:
                # For promotional products (price_subtotal = 0)
                record.product_price_subtotal = 0
                record.product_promotion = True

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
                       partner.company_registry     AS partner_company_registry,
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

    def _select_clause(self):
        return """
            SELECT ROW_NUMBER() OVER ()   AS id,
                        line.product_id        AS product_id,
                        sol.price_unit         AS product_price_unit,
                        pt.country_of_origin   AS product_country_of_origin,
                        pt.categ_id            AS product_category_id,
                        so.sale_id,
                        so.sale_user_id,
                        so.sale_date_order,
                        so.sale_day_order,
                        so.sale_month_order,
                        so.sale_year_order,
                        so.partner_id,
                        so.partner_company_registry,
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
                so.partner_company_registry, so.street, so.wards_id, so.district_id, so.state_id, so.country_id,
                line.lot_serial_number, line.qr_code, pa.product_att_size_lop, pa.product_att_ma_gai,
                pa.product_att_rim_diameter_inch
        """

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s);" % (self._table, self.query())
        )

    def query(self):
        return f"""
              WITH 
              {self._with_clause()}
              {self._select_clause()}
              {self._from_clause()}
              {self._where_clause()}
              {self._group_by_clause()}
        """

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
            order = "sale_date_order DESC, sale_id DESC"

        return super(SalespersonReport, self).web_search_read(
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
        res = super(SalespersonReport, self).web_read_group(
            domain,
            fields,
            groupby,
            limit=limit,
            offset=offset,
            orderby=orderby,
            lazy=lazy,
        )

        # Check if 'product_template_id' is in groupby and 'product_price_unit' is in fields
        if "product_id" in groupby and "product_price_unit" in fields:
            # Iterate over the result groups
            for line in res["groups"]:
                # Adjust 'product_price_unit' by dividing it by the count of 'product_template_id'
                line["product_price_unit"] = (
                    line["product_price_unit"] / line["product_id_count"]
                )

        return res
