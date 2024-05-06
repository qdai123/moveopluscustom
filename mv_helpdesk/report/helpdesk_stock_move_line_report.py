# -*- coding: utf-8 -*-
from odoo import api, fields, models, tools, _


class HelpdeskStockMoveLineReport(models.Model):
    _name = "mv.helpdesk.stock.move.line.report"
    _description = _("Report: Helpdesk - Products Move")
    _auto = False
    _rec_name = "product_template_id"
    _order = "serial_number desc"

    @api.depends("product_template_id")
    def _compute_by_product(self):
        size_lop = "Size lốp"
        ma_gai = "Mã gai"

        for record in self:
            if record.product_template_id:
                # Fetch all attribute values for the product template
                attribute_values = self.env["product.template.attribute.value"].search(
                    [
                        ("product_tmpl_id", "=", record.product_template_id.id),
                        ("attribute_id.name", "in", [size_lop, ma_gai]),
                    ]
                )

                # Extract attribute values for "Size lốp" and "Mã gai"
                size_lop_value = attribute_values.filtered(
                    lambda r: r.attribute_id.name == size_lop
                ).product_attribute_value_id.name
                ma_gai_value = attribute_values.filtered(
                    lambda r: r.attribute_id.name == ma_gai
                ).product_attribute_value_id.name

                # Update the record fields
                record.product_att_size_lop = size_lop_value
                record.product_att_ma_gai = ma_gai_value

    # ==== Product fields ====
    product_barcode = fields.Char("Barcode", readonly=True)
    product_template_id = fields.Many2one("product.template", "Product", readonly=True)
    product_country_of_origin = fields.Many2one("res.country", "Country", readonly=True)
    product_att_size_lop = fields.Char("Size lốp", compute="_compute_by_product")
    product_att_ma_gai = fields.Char("Mã gai", compute="_compute_by_product")

    # ==== Stock fields ====
    serial_number = fields.Char("Serial Number", readonly=True)
    qrcode = fields.Char("QR-Code", readonly=True)
    week_number = fields.Char("DOT", readonly=True)

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
        return """WITH """ + ",\n    ".join(with_) if with_ else ""

    def _select_clause(self, *select):
        return "" + (
            ",\n    " + ",\n    ".join(select)
            if select
            else """
                SELECT ROW_NUMBER() OVER ()           AS id,
                           product.barcode                AS product_barcode,
                           product_tmpl.id                AS product_template_id,
                           product_tmpl.country_of_origin AS product_country_of_origin,
                           stock_ml.lot_name              AS serial_number,
                           stock_ml.qr_code               AS qrcode,
                           period.week_number_str         AS week_number,
                           ticket.id                      AS ticket_id,
                           ticket_type.name ->> 'en_US'   AS ticket_type,
                           ticket_stage.name ->> 'en_US'  AS ticket_stage,
                           ticket.write_date              AS ticket_write_date,
                           ticket.partner_id,
                           ticket.partner_email,
                           ticket.partner_phone
            """
        )

    def _from_clause(self, *join_):
        return "" + (
            "\n".join(join_) + "\n"
            if join_
            else """
                FROM product_product product
                     LEFT JOIN product_template AS product_tmpl
                               ON (product.product_tmpl_id = product_tmpl.id AND product_tmpl.detailed_type = 'product')
                     JOIN mv_helpdesk_ticket_product_moves AS ticket_product_moves
                          ON (ticket_product_moves.product_id = product.id 
                          AND ticket_product_moves.helpdesk_ticket_id IS NOT NULL)
                     JOIN stock_move_line AS stock_ml
                          ON (stock_ml.product_id = product.id AND stock_ml.id = ticket_product_moves.stock_move_line_id)
                     LEFT JOIN inventory_period AS period ON (period.id = stock_ml.inventory_period_id)
                     LEFT JOIN helpdesk_ticket AS ticket ON (ticket.id = ticket_product_moves.helpdesk_ticket_id)
                     LEFT JOIN helpdesk_ticket_type AS ticket_type ON (ticket_type.id = ticket.ticket_type_id)
                     LEFT JOIN helpdesk_stage AS ticket_stage ON (ticket_stage.id = ticket.stage_id)
            """
        )

    def _group_by_clause(self, *group_by):
        return (
            "" + ",\n    ".join(group_by)
            if group_by
            else """
                GROUP BY product_barcode,
                              product_template_id,
                              product_country_of_origin,
                              serial_number,
                              qrcode,
                              week_number,
                              ticket_id,
                              ticket_type,
                              ticket_stage,
                              ticket_write_date,
                              ticket.partner_id,
                              ticket.partner_email,
                              ticket.partner_phone
            """
        )
