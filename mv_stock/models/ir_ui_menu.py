# -*- coding: utf-8 -*-
from odoo import models, api, tools


class Menu(models.Model):
    _inherit = 'ir.ui.menu'

    @api.model
    @tools.ormcache('frozenset(self.env.user.groups_id.ids)', 'debug')
    def _visible_menu_ids(self, debug=False):
        menus = super(Menu, self)._visible_menu_ids(debug)
        move_history_menu = self.env.ref(
            "stock.stock_move_line_menu", raise_if_not_found=False)
        move_analysis_menu = self.env.ref(
            "stock.stock_move_menu", raise_if_not_found=False)
        hide_menu_access_ids = [move_history_menu, move_analysis_menu]
        if self.env.user.has_group('mv_stock.mv_show_inventory_report_group'):
            for rec in hide_menu_access_ids:
                menus.discard(rec.id)
            return menus
        return menus
