# -*- coding: utf-8 -*-
from odoo import SUPERUSER_ID, _, api, fields, models, tools


class MvBrand(models.Model):
    """Brand for Partner Survey"""

    _name = "mv.brand"
    _description = _("Brand")
    _order = "priority desc, name, id"

    @tools.ormcache()
    def _get_default_category_id(self):
        # Deletion forbidden (at least through unlink)
        return self.env.ref("mv_dms.brand_category_all")

    @tools.ormcache()
    def _get_default_uom_id(self):
        # Deletion forbidden (at least through unlink)
        return self.env.ref("uom.product_uom_unit")

    def _read_group_categ_id(self, categories, domain, order):
        category_ids = self.env.context.get("default_mv_brand_categ_id")
        if not category_ids and self.env.context.get("group_expand"):
            category_ids = categories._search(
                [], order=order, access_rights_uid=SUPERUSER_ID
            )
        return categories.browse(category_ids)

    active = fields.Boolean(default=True)
    sequence = fields.Integer("Thứ tự", default=1)
    default_code = fields.Char("Mã tham chiếu", index=True)
    name = fields.Char("Thương hiệu", index="trigram", required=True, translate=True)
    description = fields.Html("Mô tả", translate=True)
    uom_id = fields.Many2one(
        "uom.uom",
        "Đơn vị",
        default=_get_default_uom_id,
        required=True,
    )
    uom_name = fields.Char(
        "Tên đơn vị",
        related="uom_id.name",
        readonly=True,
    )
    mv_brand_categ_id = fields.Many2one(
        "mv.brand.category",
        "Danh mục thương hiệu",
        change_default=True,
        default=_get_default_category_id,
        group_expand="_read_group_categ_id",
        required=True,
    )
    priority = fields.Selection(
        [
            ("0", "Normal"),
            ("1", "Favorite"),
        ],
        "Yêu thích",
        default="0",
    )
    color = fields.Integer("Color Index")
    # all image fields are base64 encoded and PIL-supported
    image_1920 = fields.Image(
        "Hình ảnh",
        max_width=1024,
        max_height=1024,
        store=True,
    )
    image_1024 = fields.Image(
        related="image_1920",
        max_width=1024,
        max_height=1024,
        store=True,
    )
    image_512 = fields.Image(
        related="image_1920",
        max_width=512,
        max_height=512,
        store=True,
    )
    image_256 = fields.Image(
        related="image_1920",
        max_width=256,
        max_height=256,
        store=True,
    )
    image_128 = fields.Image(
        related="image_1920",
        max_width=128,
        max_height=128,
        store=True,
    )

    _sql_constraints = [
        (
            "name_uniq",
            "unique(name)",
            "Tên thương hiệu đã tồn tại, vui lòng chọn tên khác!",
        )
    ]

    @api.model
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        if args is None:
            args = []

        args += self._get_contextual_brand_filter()
        return super(MvBrand, self).name_search(name, args, operator, limit)

    def _get_contextual_brand_filter(self):
        search_context = dict(self.env.context or {})
        brand_filter = []

        if search_context.get("search_default_brand_tire"):
            brand_tire = self.env.ref("mv_dms.brand_category_tire")
            brand_filter = [("mv_brand_categ_id", "=", brand_tire.id)]
        elif search_context.get("search_default_brand_lubricant"):
            brand_lubricant = self.env.ref("mv_dms.brand_category_lubricant")
            brand_filter = [("mv_brand_categ_id", "=", brand_lubricant.id)]
        elif search_context.get("search_default_brand_battery"):
            brand_battery = self.env.ref("mv_dms.brand_category_battery")
            brand_filter = [("mv_brand_categ_id", "=", brand_battery.id)]

        return brand_filter

    def _get_placeholder_filename(self, field):
        image_fields = ["image_%s" % size for size in [1920, 1024, 512, 256, 128]]
        if field in image_fields:
            return "mv_dms/static/img/placeholder_thumbnail.png"
        return super()._get_placeholder_filename(field)
