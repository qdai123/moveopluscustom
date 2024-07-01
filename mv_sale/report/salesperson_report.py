# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _


class SalespersonReport(models.Model):
    _name = "salesperson.report"
    _description = _("Salesperson's Analysis Report")
    _auto = False
    _rec_name = "product_template_id"
    _rec_names_search = ["sale_id", "sale_ref", "partner_id", "serial_number"]
    _order = "sale_date_order desc"

    # ==== Product FIELDS ==== #
    product_id = fields.Many2one("product.product", readonly=True)
    product_barcode = fields.Char(readonly=True)
    product_template_id = fields.Many2one("product.template", readonly=True)
    product_country_of_origin = fields.Many2one("res.country", readonly=True)
    product_att_size_lop = fields.Char(readonly=True)
    product_att_ma_gai = fields.Char(readonly=True)
    product_att_rim_diameter_inch = fields.Char(readonly=True)
    # ==== Stock FIELDS ==== #
    serial_number = fields.Char(readonly=True)
    qrcode = fields.Char(readonly=True)
    week_number = fields.Many2one("inventory.period", readonly=True)
    # ==== Sale FIELDS ==== #
    sale_id = fields.Many2one("sale.order", readonly=True)
    sale_ref = fields.Char(compute="_compute_sale_id")
    sale_date_order = fields.Date(compute="_compute_sale_id")
    sale_day_order = fields.Char(compute="_compute_sale_id")
    sale_month_order = fields.Char(compute="_compute_sale_id")
    sale_year_order = fields.Char(compute="_compute_sale_id")
    # ==== Partner FIELDS ==== #
    partner_id = fields.Many2one("res.partner", readonly=True)
    partner_shipping_id = fields.Many2one("res.partner", readonly=True)
    delivery_address = fields.Char(compute="_compute_partner_shipping_id")
    street = fields.Char(compute="_compute_partner_shipping_id")
    country_id = fields.Many2one("res.country", compute="_compute_partner_shipping_id")
    state_id = fields.Many2one(
        "res.country.state", compute="_compute_partner_shipping_id"
    )
    district_id = fields.Many2one(
        "res.country.district", compute="_compute_partner_shipping_id"
    )
    wards_id = fields.Many2one(
        "res.country.wards", compute="_compute_partner_shipping_id"
    )

    @api.depends("sale_id")
    def _compute_sale_id(self):
        for record in self:
            if record.sale_id:
                record.sale_ref = record.sale_id.name
                record.sale_date_order = record.sale_id.date_order.date()
                record.sale_day_order = record.sale_id.date_order.day
                record.sale_month_order = record.sale_id.date_order.month
                record.sale_year_order = record.sale_id.date_order.year

    @api.depends("partner_shipping_id")
    def _compute_partner_shipping_id(self):
        for record in self:
            if record.partner_shipping_id:
                record.delivery_address = record.partner_shipping_id.full_address_vi
                record.street = record.partner_shipping_id.street
                record.country_id = record.partner_shipping_id.country_id
                record.state_id = record.partner_shipping_id.state_id
                record.district_id = record.partner_shipping_id.district_id
                record.wards_id = record.partner_shipping_id.wards_id

    # ==================================
    # SQL Queries / Initialization
    # ==================================

    @api.model
    def _sql_orders(self):
        return f"""
            SELECT so.id AS sale_id,
                       so.partner_id,
                       so.partner_shipping_id
                FROM sale_order so
                         JOIN res_partner rp ON so.partner_id = rp.id
                WHERE so.state = 'sale'
                  AND rp.is_agency = TRUE
                GROUP BY so.id, so.partner_id, so.partner_shipping_id
        """

    def _query(self):
        return f"""
              WITH {self._with_clause()}
              {self._select_clause()}
              {self._from_clause()}
              {self._where_clause()}
              {self._group_by_clause()}
        """

    def _with_clause(self):
        return f"""
            orders AS ({self._sql_orders()}),
            order_lines AS (SELECT so.*,
                            sml.lot_name            AS serial_number,
                            sml.qr_code             AS qrcode,
                            sml.inventory_period_id AS week_number,
                            sol.product_id
                     FROM sale_order_line AS sol
                              JOIN orders AS so ON (so.sale_id = sol.order_id)
                              JOIN product_product AS pp ON (pp.id = sol.product_id)
                              JOIN product_template AS pt
                                   ON (pt.id = pp.product_tmpl_id) AND pt.detailed_type = 'product'
                              JOIN stock_picking AS sp ON (sp.sale_id = sol.order_id) AND sp.state != 'draft'
                              JOIN stock_move_line AS sml
                                   ON (sml.picking_id = sp.id AND sml.product_id = sol.product_id)
                     WHERE sol.state = 'sale'
                       AND sol.qty_delivered_method = 'stock_move'),
     products AS (SELECT pp.id                AS product_id,
                         pp.barcode           AS product_barcode,
                         pt.id                AS product_template_id,
                         pt.country_of_origin AS product_country_of_origin
                  FROM product_product AS pp
                           JOIN product_template AS pt
                                ON (pt.id = pp.product_tmpl_id
                                       ) AND
                                   pp.id IN (SELECT product_id
                                             FROM order_lines)
                  WHERE pp.id IN (SELECT product_id
                                  FROM order_lines)
                    AND pt.detailed_type = 'product'),
     products_size_lop AS (SELECT pp.id                               AS product_id,
                                  pav_size_lop.name ->> 'en_US'::TEXT AS product_att_size_lop
                           FROM product_product AS pp
                                    JOIN product_template AS pt ON (pt.id = pp.product_tmpl_id
                                                                       ) AND
                                                                   pp.id IN
                                                                   (SELECT product_id
                                                                    FROM order_lines)
                                    JOIN product_template_attribute_line AS ptal ON (ptal.product_tmpl_id = pt.id
                               )
                                    JOIN product_attribute AS pa_size_lop
                                         ON (pa_size_lop.id = ptal.attribute_id
                                                ) AND
                                            pa_size_lop.attribute_code IN ('size_lop'
                                                )
                                    JOIN product_template_attribute_value AS ptav_size_lop
                                         ON (ptav_size_lop.product_tmpl_id = pt.id AND
                                             ptav_size_lop.attribute_id = pa_size_lop.id
                                             )
                                    JOIN product_attribute_value AS pav_size_lop
                                         ON (pav_size_lop.id = ptav_size_lop.product_attribute_value_id
                                             )
                           WHERE pp.id IN (SELECT product_id
                                           FROM products)
                           GROUP BY product_id, product_att_size_lop),
     products_ma_gai AS (SELECT pp.id                             AS product_id,
                                pav_ma_gai.name ->> 'en_US'::TEXT AS product_att_ma_gai
                         FROM product_product AS pp
                                  JOIN product_template AS pt ON (pt.id = pp.product_tmpl_id
                                                                     ) AND
                                                                 pp.id IN
                                                                 (SELECT product_id
                                                                  FROM order_lines)
                                  JOIN product_template_attribute_line AS ptal ON (ptal.product_tmpl_id = pt.id
                             )
                                  JOIN product_attribute AS pa_ma_gai
                                       ON (pa_ma_gai.id = ptal.attribute_id
                                              ) AND pa_ma_gai.attribute_code IN ('ma_gai'
                                           )
                                  JOIN product_template_attribute_value AS ptav_ma_gai
                                       ON (ptav_ma_gai.product_tmpl_id = pt.id AND
                                           ptav_ma_gai.attribute_id = pa_ma_gai.id
                                           )
                                  JOIN product_attribute_value AS pav_ma_gai
                                       ON (pav_ma_gai.id = ptav_ma_gai.product_attribute_value_id
                                           )
                         WHERE pp.id IN (SELECT product_id
                                         FROM products)
                         GROUP BY product_id, product_att_ma_gai),
     products_rim_diameter_inch AS (SELECT pp.id                             AS product_id,
                                           pav_ma_gai.name ->> 'en_US'::TEXT AS product_att_rim_diameter_inch
                                    FROM product_product AS pp
                                             JOIN product_template AS pt ON (pt.id = pp.product_tmpl_id
                                                                                ) AND
                                                                            pp.id IN
                                                                            (SELECT product_id
                                                                             FROM order_lines)
                                             JOIN product_template_attribute_line AS ptal
                                                  ON (ptal.product_tmpl_id = pt.id
                                                      )
                                             JOIN product_attribute AS pa_ma_gai
                                                  ON (pa_ma_gai.id = ptal.attribute_id
                                                         ) AND pa_ma_gai.attribute_code IN ('rim_diameter_inch'
                                                      )
                                             JOIN product_template_attribute_value AS ptav_ma_gai
                                                  ON (ptav_ma_gai.product_tmpl_id = pt.id AND
                                                      ptav_ma_gai.attribute_id = pa_ma_gai.id
                                                      )
                                             JOIN product_attribute_value AS pav_ma_gai
                                                  ON (pav_ma_gai.id = ptav_ma_gai.product_attribute_value_id
                                                      )
                                    WHERE pp.id IN (SELECT product_id
                                                    FROM products)
                                    GROUP BY product_id, product_att_rim_diameter_inch)
        """

    def _select_clause(self):
        return """
            SELECT ROW_NUMBER() OVER ()               AS id,
                   line.*,
                   p.product_barcode                  AS product_barcode,
                   p.product_template_id              AS product_template_id,
                   p.product_country_of_origin        AS product_country_of_origin,
                   pzl.product_att_size_lop           AS product_att_size_lop,
                   pmg.product_att_ma_gai             AS product_att_ma_gai,
                   prim.product_att_rim_diameter_inch AS product_att_rim_diameter_inch
        """

    def _from_clause(self):
        return """
            FROM order_lines line
                 JOIN products AS p ON (p.product_id = line.product_id)
                 FULL OUTER JOIN products_size_lop pzl ON (p.product_id = pzl.product_id)
                 FULL OUTER JOIN products_ma_gai pmg ON (p.product_id = pmg.product_id)
                 FULL OUTER JOIN products_rim_diameter_inch prim ON (p.product_id = prim.product_id)
        """

    def _where_clause(self):
        return ""

    def _group_by_clause(self):
        return "GROUP BY 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14"

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s);" % (self._table, self._query())
        )
