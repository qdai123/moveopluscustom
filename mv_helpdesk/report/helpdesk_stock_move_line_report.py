# -*- coding: utf-8 -*-
from odoo import fields, models, tools, _


class HelpdeskStockMoveLineReport(models.Model):
    _name = "mv.helpdesk.stock.move.line.report"
    _description = _("Report: Helpdesk - Products Move")
    _auto = False
    _rec_name = "product_template_id"
    _order = "serial_number desc"

    # ==== Stock fields ====
    serial_number = fields.Char("Serial Number", readonly=True)
    qrcode = fields.Char("QR-Code", readonly=True)
    week_number = fields.Char("DOT", readonly=True)

    # ==== Product fields ====
    product_id = fields.Many2one(
        "product.product", readonly=True, help="Invisible field!"
    )
    product_template_id = fields.Many2one("product.template", "Product", readonly=True)
    product_barcode = fields.Char("Barcode", readonly=True)
    product_country_of_origin = fields.Many2one("res.country", "Country", readonly=True)
    product_att_size_lop = fields.Char("Size lốp", readonly=True)
    product_att_ma_gai = fields.Char("Mã gai", readonly=True)

    # ==== Helpdesk fields ====
    ticket_id = fields.Many2one("helpdesk.ticket", "Ticket", readonly=True)
    ticket_type = fields.Char("Ticket Type", readonly=True)
    ticket_stage = fields.Char("Ticket Stage", readonly=True)
    ticket_write_date = fields.Datetime("Last Updated On", readonly=True)
    partner_id = fields.Many2one("res.partner", readonly=True)
    partner_email = fields.Char("Email", readonly=True)
    partner_phone = fields.Char("Phone", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s);" % (self._table, self._query())
        )

    def _query(self, with_=None, select=None, join=None, group_by=None):
        return "\n".join(
            [
                self._with_clause(*(with_ or [])),
                self._select_clause(*(select or [])),
                self._from_clause(*(join or [])),
                self._group_by_clause(*(group_by or [])),
            ]
        )

    def _with_clause(self, *with_):
        return (
            """
WITH 
    """
            + ",\n    ".join(with_)
            if with_
            else """
WITH products AS (SELECT pp.id                AS product_product_id,
                         pt.id                AS product_template_id,
                         pt.country_of_origin AS product_country_of_origin,
                         pp.barcode           AS product_barcode
                  FROM product_template pt
                           JOIN product_product pp ON pt.id = pp.product_tmpl_id
                  WHERE pt.type = 'product'
                  GROUP BY 1, 2, 3, 4),
     products_first_attribute AS (SELECT attribute.id                   AS attribute_id,
                                         attribute.name ->> 'en_US'     AS attribute_name,
                                         attribute_val.id               AS attribute_value_id,
                                         attribute_val.name ->> 'en_US' AS attribute_value,
                                         ptattline.product_tmpl_id      AS product_template_id
                                  FROM product_attribute attribute
                                           JOIN product_attribute_value attribute_val
                                                ON attribute.id = attribute_val.attribute_id
                                           JOIN product_template_attribute_line ptattline
                                                ON attribute.id = ptattline.attribute_id
                                  WHERE attribute.name ->> 'en_US' = 'Size lốp'
                                  GROUP BY attribute.id, 2, 3, 4, 5
                                  ORDER BY attribute.id),
     products_second_attribute AS (SELECT attribute.id                   AS attribute_id,
                                          attribute.name ->> 'en_US'     AS attribute_name,
                                          attribute_val.id               AS attribute_value_id,
                                          attribute_val.name ->> 'en_US' AS attribute_value,
                                          ptattline.product_tmpl_id      AS product_template_id
                                   FROM product_attribute attribute
                                            JOIN product_attribute_value attribute_val
                                                 ON attribute.id = attribute_val.attribute_id
                                            JOIN product_template_attribute_line ptattline
                                                 ON attribute.id = ptattline.attribute_id
                                   WHERE attribute.name ->> 'en_US' = 'Mã gai'
                                   GROUP BY attribute.id, 2, 3, 4, 5
                                   ORDER BY attribute.id),
     tickets AS (SELECT ticket.id                    AS ticket_id,
                        ticket_type.name ->> 'en_US' AS ticket_type,
                        hs.name ->> 'en_US'          AS ticket_stage,
                        ticket.write_date            AS ticket_write_date,
                        ticket.partner_id            AS partner_id,
                        ticket.partner_email         AS partner_email,
                        ticket.partner_phone         AS partner_phone,
                        hpm.stock_move_line_id       AS move_line_id
                 FROM helpdesk_ticket ticket
                          JOIN helpdesk_ticket_type AS ticket_type ON (ticket.ticket_type_id = ticket_type.id)
                          JOIN helpdesk_stage AS hs ON (ticket.stage_id = hs.id)
                          JOIN mv_helpdesk_ticket_product_moves AS hpm ON (ticket.id = hpm.helpdesk_ticket_id)
                 WHERE hs.name ->> 'en_US' = 'Done'
                 GROUP BY 1, 2, 3, 4, 5, 6, 7, 8)
            """
        )

    def _select_clause(self, *select):
        return "" + (
            ",\n    " + ",\n    ".join(select)
            if select
            else """
SELECT ROW_NUMBER() OVER ()        AS id,
       sml.lot_name                AS serial_number,
       sml.product_id              AS product_id,
       p.product_template_id       AS product_template_id,
       patt_first.attribute_value  AS product_att_size_lop,
       patt_second.attribute_value AS product_att_ma_gai,
       p.product_country_of_origin AS product_country_of_origin,
       p.product_barcode           AS product_barcode,
       sml.qr_code                 AS qrcode,
       sml.inventory_period_name   AS week_number,
       t.ticket_id,
       t.ticket_type,
       t.ticket_stage,
       t.ticket_write_date,
       t.partner_id,
       t.partner_email,
       t.partner_phone
            """
        )

    def _from_clause(self, *join_):
        return "" + (
            "\n".join(join_) + "\n"
            if join_
            else """
FROM stock_move_line sml
         INNER JOIN tickets AS t ON (t.move_line_id = sml.id)
         INNER JOIN products AS p ON (p.product_product_id = sml.product_id)
         LEFT JOIN products_first_attribute AS patt_first
                   ON (patt_first.product_template_id = p.product_template_id)
         LEFT JOIN products_second_attribute AS patt_second
                   ON (patt_second.product_template_id = p.product_template_id)
            """
        )

    def _group_by_clause(self, *group_by):
        return (
            "" + ",\n    ".join(group_by)
            if group_by
            else "GROUP BY 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17"
        )
