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
    _order = "sale_id DESC, serial_number"

    # ==== Product FIELDS ==== #
    product_id = fields.Many2one("product.product", "Base Product", readonly=True)
    product_template_id = fields.Many2one("product.template", "Sản phẩm", readonly=True)
    product_country_of_origin = fields.Many2one(
        "res.country", "Quốc Gia (Sản phẩm)", readonly=True
    )
    product_category_id = fields.Many2one(
        "product.category", "Danh mục sản phẩm", readonly=True
    )
    product_att_size_lop = fields.Char("Size (lốp)", readonly=True)
    product_att_ma_gai = fields.Char("Mã gai", readonly=True)
    product_att_rim_diameter_inch = fields.Char("Đường kính Mâm", readonly=True)
    # ==== Stock FIELDS ==== #
    serial_number = fields.Char("Mã vạch", readonly=True)
    qrcode = fields.Char("QR-Code", readonly=True)
    # ==== Sale FIELDS ==== #
    sale_id = fields.Many2one("sale.order", "Mã đơn hàng", readonly=True)
    sale_user_id = fields.Many2one("res.users", "Nhân viên kinh doanh", readonly=True)
    sale_date_order = fields.Date("Ngày đặt hàng", readonly=True)
    sale_day_order = fields.Char("Ngày", readonly=True)
    sale_month_order = fields.Char("Tháng", readonly=True)
    sale_year_order = fields.Char("Năm", readonly=True)
    # ==== Partner FIELDS ==== #
    partner_id = fields.Many2one("res.partner", "Đại lý", readonly=True)
    partner_company_registry = fields.Char("Mã Đại lý", readonly=True)
    street = fields.Char("Đường", readonly=True)
    wards_id = fields.Many2one("res.country.wards", "Phường", readonly=True)
    district_id = fields.Many2one("res.country.district", "Quận", readonly=True)
    state_id = fields.Many2one("res.country.state", "Thành phố", readonly=True)
    country_id = fields.Many2one("res.country", "Quốc gia", readonly=True)
    delivery_address = fields.Char("Địa chỉ giao hàng", compute="_compute_sale_id")

    @api.depends("sale_id", "sale_id.partner_shipping_id")
    def _compute_sale_id(self):
        for record in self:
            order = record.sale_id.sudo()
            if order and order.partner_shipping_id:
                record.delivery_address = order.partner_shipping_id.full_address_vi

    # ==================================
    # SQL Queries / Initialization
    # ==================================

    @api.model
    def _sql_orders(self):
        AND_CLAUSE = (
            (
                """
            AND (so.is_order_returns = FALSE OR so.is_order_returns IS NULL)
            AND (so.user_id = %s OR so.user_id IS NULL)
        """
                % self.env.user.id
            )
            if self.env.user.has_group(GROUP_SALESPERSON)
            else "AND (so.is_order_returns = FALSE OR so.is_order_returns IS NULL)"
        )
        return f"""
            SELECT so.id                             AS sale_id,
                   so.user_id                        AS sale_user_id,
                   so.date_order::DATE               AS sale_date_order,
                   EXTRACT(DAY FROM so.date_order)   AS sale_day_order,
                   EXTRACT(MONTH FROM so.date_order) AS sale_month_order,
                   EXTRACT(YEAR FROM so.date_order)  AS sale_year_order,
                   partner.id                        AS partner_id,
                   partner.company_registry          AS partner_company_registry,
                   partner_shipping.street,
                   partner_shipping.wards_id,
                   partner_shipping.district_id,
                   partner_shipping.state_id,
                   partner_shipping.country_id
            FROM sale_order so
                     INNER JOIN res_partner partner ON (so.partner_id = partner.id AND partner.is_agency = TRUE)
                     INNER JOIN res_partner partner_shipping ON (so.partner_shipping_id = partner_shipping.id)
            WHERE so.state = 'sale'
                {AND_CLAUSE}
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
        return f"""
            orders AS ({self._sql_orders()}),
            order_lines AS (SELECT so.sale_id,
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
                                   pp.id                AS product_id,
                                   pt.id                AS product_template_id,
                                   pt.country_of_origin AS product_country_of_origin,
                                   pt.categ_id          AS product_category_id,
                                   stl.name             AS serial_number,
                                   stl.ref              AS qrcode
                             FROM sale_order_line sol
                                  JOIN orders so ON so.sale_id = sol.order_id
                                  JOIN product_product pp ON pp.id = sol.product_id
                                  JOIN product_template pt ON pt.id = pp.product_tmpl_id
                                  JOIN stock_picking sp ON sp.sale_id = sol.order_id
                                  JOIN stock_move_line sml ON sml.picking_id = sp.id AND sml.product_id = pp.id
                                  JOIN stock_lot stl ON stl.id = sml.lot_id AND stl.product_id = pp.id
                             WHERE sol.state = 'sale'
                               AND sol.qty_delivered_method = 'stock_move'
                               AND pt.sale_ok = TRUE
                               AND (pt.detailed_type = 'product' OR pt.type = 'product')
                               AND sp.state = 'done'),
        product_attributes AS (SELECT pp.id                                      AS product_id,
                                       MAX(CASE
                                               WHEN paatt.attribute_code IN ('{att_size_lop}', '{att_size_lop}_duplicated')
                                                   THEN pav.name ->> 'en_US' END) AS product_att_size_lop,
                                       MAX(CASE
                                               WHEN paatt.attribute_code IN ('{att_ma_gai}', '{att_ma_gai}_duplicated')
                                                   THEN pav.name ->> 'en_US' END) AS product_att_ma_gai,
                                       MAX(CASE
                                               WHEN paatt.attribute_code IN ('{att_rim_diameter_inch}', '{att_rim_diameter_inch}_duplicated')
                                                   THEN pav.name ->> 'en_US' END) AS product_att_rim_diameter_inch
                                FROM product_product pp
                                         JOIN product_template pt ON pt.id = pp.product_tmpl_id
                                         JOIN product_template_attribute_line ptal ON ptal.product_tmpl_id = pt.id
                                         JOIN product_attribute paatt ON paatt.id = ptal.attribute_id
                                         JOIN product_template_attribute_value ptav ON ptav.product_tmpl_id = pt.id AND ptav.attribute_id = paatt.id
                                         JOIN product_attribute_value pav ON pav.id = ptav.product_attribute_value_id
                                WHERE pp.id IN (SELECT product_id FROM order_lines)
                                GROUP BY pp.id)
        """

    def _select_clause(self):
        return """
            SELECT ROW_NUMBER() OVER () AS id,
                   line.*,
                   pa.product_att_size_lop,
                   pa.product_att_ma_gai,
                   pa.product_att_rim_diameter_inch
        """

    def _from_clause(self):
        return """
            FROM order_lines line
                JOIN product_attributes pa ON pa.product_id = line.product_id
        """

    def _where_clause(self):
        return ""

    def _group_by_clause(self):
        return """
            GROUP BY line.sale_id,
                     line.sale_user_id,
                     line.sale_date_order,
                     line.sale_day_order,
                     line.sale_month_order,
                     line.sale_year_order,
                     line.partner_id,
                     line.partner_company_registry,
                     line.street,
                     line.wards_id,
                     line.district_id,
                     line.state_id,
                     line.country_id,
                     line.product_id,
                     line.product_template_id,
                     line.product_country_of_origin,
                     line.product_category_id,
                     line.serial_number,
                     line.qrcode,
                     pa.product_att_size_lop,
                     pa.product_att_ma_gai,
                     pa.product_att_rim_diameter_inch
        """

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s);" % (self._table, self._query())
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

        return super(SalespersonReport, self).web_search_read(
            domain,
            specification,
            offset=offset,
            limit=limit,
            order=order,
            count_limit=count_limit,
        )
