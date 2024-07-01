# -*- coding: utf-8 -*-
import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)

MODELS_ZNS_USE_TYPE = [
    ("stock.picking", "stock.picking"),
    ("stock.move", "stock.move"),
    ("stock.move.line", "stock.move.line"),
    ("account.move", "account.move"),
    ("account.move.line", "account.move.line"),
]


class ZNSTemplates(models.Model):
    _inherit = "zns.template"

    active = fields.Boolean(default=True)

    # === Fields OVERRIDE ===#
    use_type = fields.Selection(selection_add=MODELS_ZNS_USE_TYPE)
