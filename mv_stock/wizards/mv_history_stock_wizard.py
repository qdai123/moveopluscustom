from odoo import models, fields, api, _


class MVHistoryStockWizard(models.TransientModel):
    _name = "mv.history.stock.wizard"
    _description = _("Wizard: MV History Stock")

    date_from = fields.Datetime('Từ ngày', required=True)
    date_to = fields.Datetime('Đến ngày', required=True)

    def export_stock(self):
        self.ensure_one()
        products = self.env['product.product'].search([
            ('detailed_type', '=', 'product')
        ])
        self.env['mv.history.stock'].search([
            ('create_uid', '=', self.env.user.id)
        ]).unlink()
        history_stocks = self.env['mv.history.stock']
        sequence = 1
        for product in products:
            stock = self.env['mv.history.stock'].create({
                'product_id': product.id,
                'date_from': self.date_from,
                'report_date_from': self.date_from.date().strftime("%d/%m/%Y"),
                'date_to': self.date_to,
                'report_date_to': self.date_to.date().strftime("%d/%m/%Y"),
                'sequence': sequence,
            })
            sequence += 1
            history_stocks |= stock
        return {
            'type': 'ir.actions.act_window',
            'name': _("Xuất/Nhập tồn"),
            'res_model': 'mv.history.stock',
            'view_mode': 'tree',
            'views': [(self.env.ref('mv_stock.mv_history_stock_view_tree').id, 'tree')],
            'domain': [('id', 'in', history_stocks.ids)],
            'context': {},
            'target': 'current',
        }
