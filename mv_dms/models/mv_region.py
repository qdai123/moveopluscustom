# -*- coding: utf-8 -*-
from odoo import _, fields, models


class MvRegion(models.Model):
    _name = "mv.region"
    _description = _("Region")
    _rec_name = "name"

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
        "mv_region_res_country_rel",
        "region_id",
        "country_id",
        string="Countries",
    )  # TODO: This field should be computed to get countries from regions
    parent_id = fields.Many2one(
        "mv.region",
        "Continent",
        domain="[('type', 'in', ['continent', 'region'])]",
        ondelete="cascade",
        index=True,
    )

    _sql_constraints = [
        ("name_uniq", "unique (name)", "Name must be unique"),
        ("code_type_uniq", "unique (code, type)", "Code with type must be unique"),
        (
            "parent_id_check",
            "check(parent_id != id)",
            "Parent area must not be the same as the region itself",
        ),
    ]
