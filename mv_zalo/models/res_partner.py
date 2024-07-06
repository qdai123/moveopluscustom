# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class Partner(models.Model):
    _inherit = "res.partner"

    short_name = fields.Char(string="Nick Name", help="Nick name of partner")
