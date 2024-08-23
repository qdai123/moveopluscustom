# -*- coding: utf-8 -*-
from odoo import _, fields, models


class MvRegion(models.Model):
    _name = "mv.region"
    _description = _("Region - Subregion")
    _rec_name = "area_name"

    active = fields.Boolean(default=True)
    area_name = fields.Char("Name", required=True)
    area_code = fields.Char("Code")
    area_type = fields.Selection(
        [
            ("continent", "Châu lục"),
            ("region", "Vùng"),
            ("subregion", "Tiểu vùng"),
            ("other", "Khác"),
        ],
        default="region",
        string="Type",
    )
    country_ids = fields.Many2many(
        "res.country",
        "mv_world_area_res_country_rel",
        "area_id",
        "country_id",
        string="Countries",
    )
    parent_id = fields.Many2one(
        "mv.world.area",
        "Continent",
        domain="[('area_type', 'in', ['continent', 'region'])]",
        ondelete="cascade",
        index=True,
    )

    _sql_constraints = [
        ("area_name_uniq", "unique (area_name)", "Area name must be unique"),
        ("area_code_uniq", "unique (area_code)", "Area code must be unique"),
        (
            "parent_id_check",
            "check(parent_id != id)",
            "Parent area must not be the same as the area itself",
        ),
    ]
