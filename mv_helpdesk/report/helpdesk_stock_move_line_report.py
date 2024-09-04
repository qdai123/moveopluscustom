# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _
from odoo.addons.mv_helpdesk.models.helpdesk_ticket import (
    HELPDESK_MANAGER,
    SUB_DEALER_CODE,
    END_USER_CODE,
)

HELPDESK_ACTIVATION_WARRANTY_TEAM = (
    "mv_website_helpdesk.mv_website_helpdesk_helpdesk_team_warranty_activation_form"
)


class HelpdeskStockMoveLineReport(models.Model):
    _name = "mv.helpdesk.stock.move.line.report"
    _description = _("Ticket Registered Analysis Report")
    _auto = False
    _rec_name = "product_template_id"
    _rec_names_search = ["ticket_id", "serial_number", "qrcode"]
    _order = "ticket_create_date desc"

    @api.model
    def get_default_helpdesk_activation_warranty_team(self):
        return self.env.ref(
            HELPDESK_ACTIVATION_WARRANTY_TEAM, raise_if_not_found=False
        ).id

    @api.model
    def get_new_stage(self):
        return self.env.ref("mv_website_helpdesk.warranty_stage_new").id

    @api.model
    def get_done_stage(self):
        return self.env.ref("mv_website_helpdesk.warranty_stage_done").id

    # ==== Product fields ====
    product_id = fields.Many2one("product.product", readonly=True)
    product_barcode = fields.Char(readonly=True)
    product_template_id = fields.Many2one("product.template", readonly=True)
    product_country_of_origin = fields.Many2one("res.country", readonly=True)
    product_att_size_lop = fields.Char(readonly=True)
    product_att_ma_gai = fields.Char(readonly=True)

    # ==== Stock fields ====
    stock_lot_id = fields.Many2one("stock.lot", readonly=True)
    stock_move_line_id = fields.Many2one("stock.move.line", readonly=True)
    serial_number = fields.Char(readonly=True)
    qrcode = fields.Char(readonly=True)
    week_number = fields.Many2one("inventory.period", readonly=True)

    # ==== Helpdesk Ticket fields ====
    ticket_create_date = fields.Datetime("Created On", readonly=True)
    ticket_create_day = fields.Char("Day", readonly=True)
    ticket_create_month = fields.Char("Month", readonly=True)
    ticket_create_year = fields.Char("Year", readonly=True)
    ticket_write_date = fields.Datetime("Last Updated On", readonly=True)
    ticket_id = fields.Many2one("helpdesk.ticket", readonly=True)
    ticket_ref = fields.Char(readonly=True)
    ticket_type_id = fields.Many2one("helpdesk.ticket.type", readonly=True)
    ticket_team = fields.Selection(
        [
            ("activation_warranty_team", "Team: Kích Hoạt Bảo Hành"),
            ("claim_warranty_team", "Team Yêu Cầu Bảo Hành"),
        ],
        "Business Type",
        readonly=True,
    )
    ticket_stage_id = fields.Many2one("helpdesk.stage", readonly=True)

    # ==== Partner fields ====
    parent_partner_id = fields.Many2one("res.partner", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    partner_company_registry = fields.Char(readonly=True)
    partner_email = fields.Char(readonly=True)
    partner_phone = fields.Char(readonly=True)

    # ==================================
    # SQL Queries / Initialization
    # ==================================

    @api.model
    def _sql_tickets(self):
        warranty_team_id = self.get_default_helpdesk_activation_warranty_team()
        ticket_stage_new = self.get_new_stage()
        ticket_stage_done = self.get_done_stage()
        return f"""
                SELECT t.id                                    AS ticket_id,
                        t.ticket_ref                            AS ticket_ref,
                        t.ticket_type_id                        AS ticket_type_id,
                        t.stage_id                              AS ticket_stage_id,
                        p.parent_id                             AS parent_partner_id,
                        t.partner_id,
                        p.company_registry                      AS partner_company_registry,
                        t.partner_email,
                        t.partner_phone,
                        t.create_date                           AS ticket_create_date,
                        EXTRACT(DAY FROM t.create_date)::TEXT   AS ticket_create_day,
                        EXTRACT(MONTH FROM t.create_date)::TEXT AS ticket_create_month,
                        EXTRACT(YEAR FROM t.create_date)::TEXT  AS ticket_create_year,
                        t.ticket_update_date                    AS ticket_write_date
                FROM helpdesk_ticket AS t
                    JOIN res_partner AS p ON (p.id = t.partner_id)
                WHERE t.team_id = {warranty_team_id}  AND t.stage_id IN ({ticket_stage_new}, {ticket_stage_done})
                ORDER BY t.create_date DESC
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
            tickets AS ({self._sql_tickets()}),
            ticket_product_moves AS (SELECT t.*,
                                                                   tp.stock_move_line_id,
                                                                   tp.lot_name                         AS serial_number,
                                                                   tp.qr_code                           AS qrcode,
                                                                   sml.inventory_period_id       AS week_number,
                                                                   tp.product_id
                                                    FROM mv_helpdesk_ticket_product_moves AS tp
                                                            JOIN tickets AS t ON (t.ticket_id = tp.helpdesk_ticket_id)
                                                            JOIN stock_move_line AS sml ON (sml.id = tp.stock_move_line_id)
                                                    WHERE NOT tp.product_activate_twice
                                                    ORDER BY tp.helpdesk_ticket_id DESC),
            products AS (SELECT pp.id                           AS product_id,
                                               pp.barcode                 AS product_barcode,
                                               pt.id                            AS product_template_id,
                                               pt.country_of_origin    AS product_country_of_origin
                                 FROM product_product AS pp
                                        JOIN product_template AS pt
                                                ON (pt.id = pp.product_tmpl_id) AND pp.id IN (SELECT product_id FROM ticket_product_moves)
                                WHERE pp.id IN (SELECT product_id FROM ticket_product_moves)
                                    AND pt.detailed_type = 'product'),
            products_size_lop AS (SELECT pp.id                                          AS product_id,
                                                             pav_size_lop.name ->> 'en_US'  AS product_att_size_lop
                                                FROM product_product AS pp
                                                    JOIN product_template AS pt 
                                                        ON (pt.id = pp.product_tmpl_id) AND pp.id IN (SELECT product_id FROM ticket_product_moves)
                                                    JOIN product_template_attribute_line AS ptal ON (ptal.product_tmpl_id = pt.id)
                                                    JOIN product_attribute AS pa_size_lop
                                                        ON (pa_size_lop.id = ptal.attribute_id) AND pa_size_lop.attribute_code IN ('size_lop')
                                                    JOIN product_template_attribute_value AS ptav_size_lop
                                                        ON (ptav_size_lop.product_tmpl_id = pt.id AND ptav_size_lop.attribute_id = pa_size_lop.id)
                                                    JOIN product_attribute_value AS pav_size_lop
                                                        ON (pav_size_lop.id = ptav_size_lop.product_attribute_value_id)
                                                WHERE pp.id IN (SELECT product_id FROM products)
                                                GROUP BY product_id, product_att_size_lop),
            products_ma_gai AS (SELECT pp.id                                            AS product_id,
                                                           pav_ma_gai.name ->> 'en_US'      AS product_att_ma_gai
                                             FROM product_product AS pp
                                                JOIN product_template AS pt 
                                                    ON (pt.id = pp.product_tmpl_id) AND pp.id IN (SELECT product_id FROM ticket_product_moves)
                                                JOIN product_template_attribute_line AS ptal ON (ptal.product_tmpl_id = pt.id)
                                                JOIN product_attribute AS pa_ma_gai
                                                    ON (pa_ma_gai.id = ptal.attribute_id) AND pa_ma_gai.attribute_code IN ('ma_gai')
                                                JOIN product_template_attribute_value AS ptav_ma_gai
                                                    ON (ptav_ma_gai.product_tmpl_id = pt.id AND ptav_ma_gai.attribute_id = pa_ma_gai.id)
                                                JOIN product_attribute_value AS pav_ma_gai
                                                    ON (pav_ma_gai.id = ptav_ma_gai.product_attribute_value_id)
                                 WHERE pp.id IN (SELECT product_id FROM products)
                                 GROUP BY product_id, product_att_ma_gai)
        """

    def _select_clause(self):
        return """
            SELECT ROW_NUMBER() OVER ()               AS id,
                          t.*,
                          p.product_barcode                        AS product_barcode,
                          p.product_template_id                    AS product_template_id,
                          p.product_country_of_origin              AS product_country_of_origin,
                          pzl.product_att_size_lop                 AS product_att_size_lop,
                          pmg.product_att_ma_gai                   AS product_att_ma_gai
        """

    def _from_clause(self):
        return """
            FROM ticket_product_moves t
                JOIN products AS p ON (p.product_id = t.product_id)
                FULL OUTER JOIN products_size_lop pzl ON (p.product_id = pzl.product_id)
                FULL OUTER JOIN products_ma_gai pmg ON (p.product_id = pmg.product_id)
        """

    def _where_clause(self):
        return ""

    def _group_by_clause(self):
        return ""

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s);" % (self._table, self._query())
        )
