# -*- coding: utf-8 -*-

from odoo import models, api, fields


class MvDiscountPartner(models.Model):
    _name = 'mv.discount.partner'

    parent_id = fields.Many2one("mv.discount")
    partner_id = fields.Many2one("res.partner", string="Partner")
    level = fields.Integer("Level")
    date = fields.Date("Date effective")
    min_debt = fields.Integer(string="Min debt")
    max_debt = fields.Integer(string="Max debt")
    number_debt = fields.Float(string="Ratio Debt")
