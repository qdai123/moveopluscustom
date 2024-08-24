# -*- coding: utf-8 -*-
from odoo import _, fields, models


class MvRegion(models.Model):
    _name = "mv.region"
    _description = _("Region")
    _rec_name = "area_name"

    active = fields.Boolean(default=True)
    name = fields.Char("Name", required=True)
    code = fields.Char("Code")
    type = fields.Selection(
        [
            ("continent", "Châu lục"),
            ("region", "Vùng"),
            ("subregion", "Tiểu vùng"),
            ("other", "Khác"),
        ],
        default="region",
        string="Type",
    )
    describe = fields.Text("Describe")
    country_ids = fields.Many2many(
        "res.country",
        "mv_world_area_res_country_rel",
        "area_id",
        "country_id",
        string="Countries",
    )  # TODO: This field should be computed to get countries from regions
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
