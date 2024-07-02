# -*- coding: utf-8 -*-
from odoo import _, api, fields, models, tools


class SalespersonReport(models.Model):
    _name = "salesperson.report"
    _description = _("Salesperson's Analysis Report")
    _auto = False
    _rec_name = "product_template_id"
    _rec_names_search = ["sale_id", "sale_ref", "partner_id", "serial_number"]
    _order = "sale_ref DESC, serial_number"

    # ==== Product FIELDS ==== #
    product_id = fields.Many2one("product.product", readonly=True)
    product_template_id = fields.Many2one("product.template", "Sản phẩm", readonly=True)
    product_country_of_origin = fields.Many2one(
        "res.country", "Quốc Gia (SP)", readonly=True
    )
    product_att_size_lop = fields.Char("Size (lốp)", readonly=True)
    product_att_ma_gai = fields.Char("Mã gai", readonly=True)
    product_att_rim_diameter_inch = fields.Char("Đường kính Mâm", readonly=True)
    # ==== Stock FIELDS ==== #
    serial_number = fields.Char("Mã vạch", readonly=True)
    qrcode = fields.Char("QR-Code", readonly=True)
    # ==== Sale FIELDS ==== #
    sale_id = fields.Many2one("sale.order", readonly=True)
    sale_ref = fields.Char("Mã SO", compute="_compute_sale_id")
    sale_date_order = fields.Date("Ngày đặt hàng", compute="_compute_sale_id")
    sale_day_order = fields.Char("Ngày đặt", compute="_compute_sale_id")
    sale_month_order = fields.Char("Tháng đặt", compute="_compute_sale_id")
    sale_year_order = fields.Char("Năm đặt", compute="_compute_sale_id")
    # ==== Partner FIELDS ==== #
    partner_id = fields.Many2one("res.partner", "Đại lý", readonly=True)
    partner_company_registry = fields.Char("Mã Đại lý", compute="_compute_partner")
    partner_shipping_id = fields.Many2one(
        "res.partner", "Đại lý vận chuyển", readonly=True
    )
    delivery_address = fields.Char("Địa chỉ giao hàng", compute="_compute_partner")
    street = fields.Char("Đường", compute="_compute_partner")
    wards_id = fields.Many2one(
        "res.country.wards", "Phường", compute="_compute_partner"
    )
    district_id = fields.Many2one(
        "res.country.district", "Quận", compute="_compute_partner"
    )
    state_id = fields.Many2one(
        "res.country.state", "Thành phố", compute="_compute_partner"
    )
    country_id = fields.Many2one("res.country", "Quốc gia", compute="_compute_partner")

    @api.depends("sale_id")
    def _compute_sale_id(self):
        for record in self:
            if record.sale_id:
                record.sale_ref = record.sale_id.name
                record.sale_date_order = record.sale_id.date_order.date()
                record.sale_day_order = record.sale_id.date_order.day
                record.sale_month_order = record.sale_id.date_order.month
                record.sale_year_order = record.sale_id.date_order.year

    @api.depends("partner_id", "partner_shipping_id")
    def _compute_partner(self):
        for record in self:
            record.partner_company_registry = record.partner_id.company_registry
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
            GROUP BY so.id
        """

    def _query(self):
        return f"""
              WITH 
              {self._with_clause()}
              {self._select_clause()}
              {self._from_clause()}
              {self._where_clause()}
              {self._group_by_clause()}
        """

    def _with_clause(self):
        att_ma_gai = self.env.context.get("attribute_ma_gai", "ma_gai")
        att_size_lop = self.env.context.get("attribute_size_lop", "size_lop")
        att_rim_diameter_inch = self.env.context.get(
            "attribute_rim_diameter_inch", "rim_diameter_inch"
        )

        print(
            f"""
            orders AS ({self._sql_orders()}),
            order_lines AS (SELECT so.sale_id,
                                so.partner_id,
                                so.partner_shipping_id,
                                sol.product_id       AS product_id,
                                pt.id                AS product_template_id,
                                pt.country_of_origin AS product_country_of_origin,
                                stl.name             AS serial_number,
                                stl.ref              AS qrcode
                         FROM sale_order_line AS sol
                                  JOIN orders AS so ON (so.sale_id = sol.order_id)
                                  JOIN product_product AS pp ON (pp.id = sol.product_id)
                                  JOIN product_template AS pt
                                       ON (pt.id = pp.product_tmpl_id)
                                           AND sale_ok = TRUE
                                           AND (pt.detailed_type = 'product' OR pt.type = 'product')
                                  JOIN stock_picking AS sp ON (sp.sale_id = sol.order_id) AND sp.state = 'done'
                                  JOIN stock_move_line AS sml ON (sml.picking_id = sp.id AND sml.product_id = pp.id)
                                  JOIN stock_lot AS stl ON (stl.id = sml.lot_id AND stl.product_id = pp.id)
                         WHERE sol.state = 'sale'
                           AND sol.qty_delivered_method = 'stock_move'
                         GROUP BY 1, 2, 3, 4, 5, 6, 7, 8),
         products AS (SELECT pp.id                         AS product_id,
                             sol.product_template_id       AS product_template_id,
                             sol.product_country_of_origin AS product_country_of_origin
                      FROM product_product AS pp
                               JOIN order_lines AS sol ON (sol.product_id = pp.id)
                      GROUP BY pp.id, sol.product_template_id, sol.product_country_of_origin),
         products_size_lop AS (SELECT pp.id                      AS product_id,
                                      pav.name ->> 'en_US'::TEXT AS product_att_size_lop
                               FROM product_product AS pp
                                        JOIN product_template AS pt
                                             ON (pt.id = pp.product_tmpl_id) AND pp.id IN (SELECT product_id FROM order_lines)
                                        JOIN product_template_attribute_line AS ptal ON (ptal.product_tmpl_id = pt.id)
                                        JOIN product_attribute AS paatt
                                             ON (paatt.id = ptal.attribute_id) AND
                                                paatt.attribute_code IN ('{att_size_lop}', '{att_size_lop}_duplicated')
                                        JOIN product_template_attribute_value AS ptav
                                             ON (ptav.product_tmpl_id = pt.id AND ptav.attribute_id = paatt.id)
                                        JOIN product_attribute_value AS pav
                                             ON (pav.id = ptav.product_attribute_value_id)
                               WHERE pp.id IN (SELECT product_id FROM products)
                               GROUP BY product_id, product_att_size_lop),
         products_ma_gai AS (SELECT pp.id                      AS product_id,
                                    pav.name ->> 'en_US'::TEXT AS product_att_ma_gai
                             FROM product_product AS pp
                                      JOIN product_template AS pt
                                           ON (pt.id = pp.product_tmpl_id) AND pp.id IN (SELECT product_id FROM order_lines)
                                      JOIN product_template_attribute_line AS ptal ON (ptal.product_tmpl_id = pt.id)
                                      JOIN product_attribute AS paatt
                                           ON (paatt.id = ptal.attribute_id) AND
                                              paatt.attribute_code IN ('{att_ma_gai}', '{att_ma_gai}_duplicated')
                                      JOIN product_template_attribute_value AS ptav
                                           ON (ptav.product_tmpl_id = pt.id AND ptav.attribute_id = paatt.id)
                                      JOIN product_attribute_value AS pav
                                           ON (pav.id = ptav.product_attribute_value_id)
                             WHERE pp.id IN (SELECT product_id FROM products)
                             GROUP BY product_id, product_att_ma_gai),
         products_rim_diameter_inch AS (SELECT pp.id                      AS product_id,
                                               pav.name ->> 'en_US'::TEXT AS product_att_rim_diameter_inch
                                        FROM product_product AS pp
                                                 JOIN product_template AS pt
                                                      ON (pt.id = pp.product_tmpl_id) AND pp.id IN (SELECT product_id FROM order_lines)
                                                 JOIN product_template_attribute_line AS ptal
                                                      ON (ptal.product_tmpl_id = pt.id)
                                                 JOIN product_attribute AS paatt
                                                      ON (paatt.id = ptal.attribute_id) AND
                                                         paatt.attribute_code IN ('{att_rim_diameter_inch}', '{att_rim_diameter_inch}_duplicated')
                                                 JOIN product_template_attribute_value AS ptav
                                                      ON (ptav.product_tmpl_id = pt.id AND ptav.attribute_id = paatt.id)
                                                 JOIN product_attribute_value AS pav
                                                      ON (pav.id = ptav.product_attribute_value_id)
                                        WHERE pp.id IN (SELECT product_id FROM products)
                                        GROUP BY product_id, product_att_rim_diameter_inch)
        """
        )

        return f"""
            orders AS ({self._sql_orders()}),
            order_lines AS (SELECT so.sale_id,
                                so.partner_id,
                                so.partner_shipping_id,
                                sol.product_id       AS product_id,
                                pt.id                AS product_template_id,
                                pt.country_of_origin AS product_country_of_origin,
                                stl.name             AS serial_number,
                                stl.ref              AS qrcode
                         FROM sale_order_line AS sol
                                  JOIN orders AS so ON (so.sale_id = sol.order_id)
                                  JOIN product_product AS pp ON (pp.id = sol.product_id)
                                  JOIN product_template AS pt
                                       ON (pt.id = pp.product_tmpl_id)
                                           AND sale_ok = TRUE
                                           AND (pt.detailed_type = 'product' OR pt.type = 'product')
                                  JOIN stock_picking AS sp ON (sp.sale_id = sol.order_id) AND sp.state = 'done'
                                  JOIN stock_move_line AS sml ON (sml.picking_id = sp.id AND sml.product_id = pp.id)
                                  JOIN stock_lot AS stl ON (stl.id = sml.lot_id AND stl.product_id = pp.id)
                         WHERE sol.state = 'sale'
                           AND sol.qty_delivered_method = 'stock_move'
                         GROUP BY 1, 2, 3, 4, 5, 6, 7, 8),
         products AS (SELECT pp.id                         AS product_id,
                             sol.product_template_id       AS product_template_id,
                             sol.product_country_of_origin AS product_country_of_origin
                      FROM product_product AS pp
                               JOIN order_lines AS sol ON (sol.product_id = pp.id)
                      GROUP BY pp.id, sol.product_template_id, sol.product_country_of_origin),
         products_size_lop AS (SELECT pp.id                      AS product_id,
                                      pav.name ->> 'en_US'::TEXT AS product_att_size_lop
                               FROM product_product AS pp
                                        JOIN product_template AS pt
                                             ON (pt.id = pp.product_tmpl_id) AND pp.id IN (SELECT product_id FROM order_lines)
                                        JOIN product_template_attribute_line AS ptal ON (ptal.product_tmpl_id = pt.id)
                                        JOIN product_attribute AS paatt
                                             ON (paatt.id = ptal.attribute_id) AND
                                                paatt.attribute_code IN ('{att_size_lop}', '{att_size_lop}_duplicated')
                                        JOIN product_template_attribute_value AS ptav
                                             ON (ptav.product_tmpl_id = pt.id AND ptav.attribute_id = paatt.id)
                                        JOIN product_attribute_value AS pav
                                             ON (pav.id = ptav.product_attribute_value_id)
                               WHERE pp.id IN (SELECT product_id FROM products)
                               GROUP BY product_id, product_att_size_lop),
         products_ma_gai AS (SELECT pp.id                      AS product_id,
                                    pav.name ->> 'en_US'::TEXT AS product_att_ma_gai
                             FROM product_product AS pp
                                      JOIN product_template AS pt
                                           ON (pt.id = pp.product_tmpl_id) AND pp.id IN (SELECT product_id FROM order_lines)
                                      JOIN product_template_attribute_line AS ptal ON (ptal.product_tmpl_id = pt.id)
                                      JOIN product_attribute AS paatt
                                           ON (paatt.id = ptal.attribute_id) AND
                                              paatt.attribute_code IN ('{att_ma_gai}', '{att_ma_gai}_duplicated')
                                      JOIN product_template_attribute_value AS ptav
                                           ON (ptav.product_tmpl_id = pt.id AND ptav.attribute_id = paatt.id)
                                      JOIN product_attribute_value AS pav
                                           ON (pav.id = ptav.product_attribute_value_id)
                             WHERE pp.id IN (SELECT product_id FROM products)
                             GROUP BY product_id, product_att_ma_gai),
         products_rim_diameter_inch AS (SELECT pp.id                      AS product_id,
                                               pav.name ->> 'en_US'::TEXT AS product_att_rim_diameter_inch
                                        FROM product_product AS pp
                                                 JOIN product_template AS pt
                                                      ON (pt.id = pp.product_tmpl_id) AND pp.id IN (SELECT product_id FROM order_lines)
                                                 JOIN product_template_attribute_line AS ptal
                                                      ON (ptal.product_tmpl_id = pt.id)
                                                 JOIN product_attribute AS paatt
                                                      ON (paatt.id = ptal.attribute_id) AND
                                                         paatt.attribute_code IN ('{att_rim_diameter_inch}', '{att_rim_diameter_inch}_duplicated')
                                                 JOIN product_template_attribute_value AS ptav
                                                      ON (ptav.product_tmpl_id = pt.id AND ptav.attribute_id = paatt.id)
                                                 JOIN product_attribute_value AS pav
                                                      ON (pav.id = ptav.product_attribute_value_id)
                                        WHERE pp.id IN (SELECT product_id FROM products)
                                        GROUP BY product_id, product_att_rim_diameter_inch)
        """

    def _select_clause(self):
        return """
            SELECT ROW_NUMBER() OVER ()               AS id,
                   line.*,
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
        return "GROUP BY 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12"

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s);" % (self._table, self._query())
        )
