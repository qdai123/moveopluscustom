from odoo import models, fields, api, _
import pytz
from datetime import datetime, time, timedelta


class MVHistoryStock(models.Model):
    _name = 'mv.history.stock'
    _description = "Moveo quantity stock history"

    date_from = fields.Datetime('Từ ngày')
    date_to = fields.Datetime('Đến ngày')
    incoming_picking_ids = fields.Many2many(
        'stock.picking', 'mv_incoming_history_stock_rel',
        'income_id', 'picking_id', string='Nhập kho')
    outgoing_picking_ids = fields.Many2many(
        'stock.picking', 'mv_outgoing_history_stock_rel',
        'outgoing_id', 'picking_id', string='Xuất kho')
    sequence = fields.Integer(default=1)
    company_id = fields.Many2one(
        'res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related="company_id.currency_id")
    product_id = fields.Many2one('product.product', string='Sản phẩm')
    uom_id = fields.Many2one(related='product_id.uom_id', store=True)
    volume = fields.Float(related='product_id.volume')
    standard_price = fields.Float(related='product_id.standard_price', store=True)
    first_quantity_stock = fields.Integer(
        'Số lượng tồn đầu kì', compute="compute_history_stocks", store=True)
    amount_first_quantity_stock = fields.Monetary(
        string="Số tiền", currency_field='currency_id', compute="compute_history_stocks", store=True)
    last_quantity_stock = fields.Integer(
        'Số lượng tồn cuối kì', compute="compute_history_stocks", store=True)
    amount_last_quantity_stock = fields.Monetary(
        string="Số tiền", currency_field='currency_id', compute="compute_history_stocks", store=True)
    incoming_quantity = fields.Integer(
        'Số lượng nhập', compute="compute_history_stocks", store=True)
    amount_incoming_quantity = fields.Monetary(
        string="Số tiền", currency_field='currency_id', compute="compute_history_stocks", store=True)
    outgoing_quantity = fields.Integer(
        'Số lượng xuất', compute="compute_history_stocks", store=True)
    amount_outgoing_quantity = fields.Monetary(
        string="Số tiền", currency_field='currency_id', compute="compute_history_stocks", store=True)
    barcode = fields.Char(related='product_id.barcode', store=True)

    # Dùng cho báo cáo xuất nhập tồn kho
    report_date_from = fields.Char('Report date from')
    report_date_to = fields.Char('Report date to')

    def calculate_all_info_stock(self):
        history_stocks = self.env['mv.history.stock'].search([
            ('create_uid', '=', self.env.user.id)
        ])
        sum_1 = sum(history_stocks.mapped('first_quantity_stock'))
        sum_2 = sum(history_stocks.mapped('amount_first_quantity_stock'))
        sum_3 = sum(history_stocks.mapped('incoming_quantity'))
        sum_4 = sum(history_stocks.mapped('amount_incoming_quantity'))
        sum_5 = sum(history_stocks.mapped('outgoing_quantity'))
        sum_6 = sum(history_stocks.mapped('amount_outgoing_quantity'))
        sum_7 = sum(history_stocks.mapped('last_quantity_stock'))
        sum_8 = sum(history_stocks.mapped('amount_last_quantity_stock'))
        return [sum_1, sum_2, sum_3, sum_4, sum_5, sum_6, sum_7, sum_8]

    def compute_first_quantity_stock(self, product, date_from, date_to):
        domain = [
            ('product_id', '=', product.id),
            ('picking_type_id', '!=', False),
            ('state', '=', 'done')
        ]

        tmp_date_from = date_from
        tmp_date_from = tmp_date_from.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone(self.env.user.tz or 'UTC'))
        first_date = datetime.combine(tmp_date_from.date() - timedelta(days=1), time(23, 59, 59))
        first_history_stocks = self.env['stock.move.line'].search(
            domain + [('date', '<=', first_date)]
        )
        tmp_in = 0
        tmp_out = 0
        for stock in first_history_stocks:
            if stock.picking_type_id.code == 'incoming':
                tmp_in += stock.quantity
            elif stock.picking_type_id.code == 'outgoing':
                tmp_out += stock.quantity
        qty_first_history_stocks = tmp_in - tmp_out

        in_out_stocks = self.env['stock.move.line'].search(
            domain + [('date', '>=', date_from), ('date', '<=', date_to)]
        )
        qty_income_stock = 0
        qty_outgoing_stock = 0
        for stock in in_out_stocks:
            if stock.picking_type_id.code == 'incoming':
                qty_income_stock += stock.quantity
            elif stock.picking_type_id.code == 'outgoing':
                qty_outgoing_stock += stock.quantity

        qty_last_history_stocks = qty_first_history_stocks + qty_income_stock - qty_outgoing_stock
        return qty_first_history_stocks, qty_income_stock, qty_outgoing_stock, qty_last_history_stocks

    @api.depends('product_id', 'date_from', 'date_to')
    def compute_history_stocks(self):
        for history in self:
            standard_price = history.standard_price if history.standard_price else 0.0
            qty_first_history_stocks, qty_income_stock, qty_outgoing_stock, qty_last_history_stocks = \
                history.compute_first_quantity_stock(history.product_id, history.date_from, history.date_to)

            history.first_quantity_stock = qty_first_history_stocks
            history.incoming_quantity = qty_income_stock
            history.outgoing_quantity = qty_outgoing_stock
            history.last_quantity_stock = qty_last_history_stocks

            history.amount_first_quantity_stock = qty_first_history_stocks * standard_price
            history.amount_last_quantity_stock = qty_last_history_stocks * standard_price
            history.amount_incoming_quantity = qty_income_stock * standard_price
            history.amount_outgoing_quantity = qty_outgoing_stock * standard_price

    def action_incoming_history(self):
        history_stocks = self.env['stock.move.line'].search([
            ('product_id', '=', self.product_id.id),
            ('picking_type_id', '!=', False),
            ('state', '=', 'done'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to)
        ]).filtered(
            lambda stock: stock.picking_type_id.code == 'incoming'
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _("Lịch sử nhập"),
            'res_model': 'stock.move.line',
            'view_mode': 'tree',
            'views': [(self.env.ref('stock.view_move_line_tree').id, 'tree')],
            'domain': [('id', 'in', history_stocks.ids)],
            'context': {},
            'target': 'new',
        }

    def action_outgoing_history(self):
        history_stocks = self.env['stock.move.line'].search([
            ('product_id', '=', self.product_id.id),
            ('picking_type_id', '!=', False),
            ('state', '=', 'done'),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to)
        ]).filtered(
            lambda stock: stock.picking_type_id.code == 'outgoing'
        )
        return {
            'type': 'ir.actions.act_window',
            'name': _("Lịch sử nhập"),
            'res_model': 'stock.move.line',
            'view_mode': 'tree',
            'views': [(self.env.ref('stock.view_move_line_tree').id, 'tree')],
            'domain': [('id', 'in', history_stocks.ids)],
            'context': {},
            'target': 'new',
        }
