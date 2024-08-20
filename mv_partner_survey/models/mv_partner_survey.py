# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class MVPartnerSurvey(models.Model):
    _name = "mv.partner.survey"
    _description = _("MV Partner Survey")
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    """
    TODO List:
    - Add fields
    - Add constraints
    - Add methods
    - Add views
    - Add security
    - Add data, demo data
    - Add tests
    - Add translations
    """

    # === RELATIONAL Fields ===#
    partner_id = fields.Many2one(
        "res.partner",
        "Đại lý",
        required=True,
        tracking=True,
        index=True,
    )
    company_id = fields.Many2one(
        "res.company",
        "Công ty",
        required=True,
        tracking=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency",
        "Tiền tệ",
        related="company_id.currency_id",
        readonly=False,
    )
    # TODO: Add more relational fields when Mr.Hieu provide these models
    # partner_area_id = fields.Many2one("mv.partner.area")
    # shop_ids = fields.One2many("mv.shop")
    # brand_proportion_ids = fields.One2many("mv.brand.proportion")
    # service_detail_ids = fields.One2many("mv.service.detail")
    # mv_product_ids = fields.Many2many("mv.product.product")

    # === BASE Fields ===#
    active = fields.Boolean(default=True, tracking=True)
    create_date = fields.Datetime("Ngày khảo sát")
    state = fields.Selection(
        [("draft", "Khảo sát"), ("done", "Hoàn thành"), ("cancel", "Hủy")],
        default="draft",
        string="Trạng thái",
        tracking=True,
    )
    name = fields.Char(
        default="SURVEY",
        readonly=True,
        index=True,
        tracking=True,
    )
    name_complete = fields.Char(
        compute="_compute_name_complete",
        store=True,
        tracking=True,
    )
    second_generation = fields.Char(
        "Thế hệ thứ 2",
        required=True,
        tracking=True,
    )
    number_of_years_bussiness = fields.Float(
        "Số năm kinh doanh",
        default=0,
        digits=(12, 2),
        required=True,
        tracking=True,
    )
    proportion = fields.Float(
        "Tỷ trọng Continental",
        default=0,
        required=True,
        tracking=True,
    )
    is_moveoplus_agency = fields.Boolean(
        "Đại lý Moveoplus",
        default=True,
        tracking=True,
    )
    classical = fields.Selection(
        [("class_a", "A"), ("class_b", "B"), ("class_c", "C")],
        default="class_a",
        string="Hạng mục",
        tracking=True,
    )
    financial_ability = fields.Selection(
        [
            ("good", "Tốt"),
            ("average", "Trung bình"),
            ("weak", "Yếu"),
        ],
        default="good",
        string="Khả năng tài chính",
        tracking=True,
    )
    # BÁN LẺ
    per_retail_customer = fields.Float("Khách hàng lẻ (%)", default=0, tracking=True)
    per_retail_taxi = fields.Float("Taxi (%)", default=0, tracking=True)
    per_retail_fleet = fields.Float("Công ty/Đội xe (%)", default=0, tracking=True)
    total_retail = fields.Float(
        "Tổng số bán lẻ (%)",
        compute="_compute_total_retail",
        store=True,
        tracking=True,
    )
    # BÁN BUÔN
    total_wholesale = fields.Float(
        "Tổng số bán buôn (%)",
        compute="_compute_total_wholesale",
        store=True,
        tracking=True,
    )
    # per_wholesale_dealer = fields.Float("Đại lý cấp 1 (%)", default=0, tracking=True)
    per_wholesale_subdealer = fields.Float("Đại lý cấp 2 (%)", default=0, tracking=True)
    per_wholesale_garage = fields.Float("Garage (%)", default=0, tracking=True)
    # DỊCH VỤ
    is_use_service = fields.Boolean("Sử dụng dịch vụ", default=False, tracking=True)
    proportion_service = fields.Float(
        "Tỷ trọng kinh doanh lốp so với dịch vụ khác (%)", default=0, tracking=True
    )
    service_bay = fields.Integer("Số lượng cầu nâng", default=0, tracking=True)
    num_technicians = fields.Integer("Số lượng kỹ thuật viên", default=0, tracking=True)
    num_sales = fields.Integer("Số lượng nhân viên bán hàng", default=0, tracking=True)
    num_administrative_staff = fields.Integer(
        "Số lượng nhân viên hành chính", default=0, tracking=True
    )

    @api.depends("partner_id", "name")
    def _compute_name_complete(self):
        for survey in self:
            if survey.partner_id:
                partner_name = (
                    survey.partner_id.short_name
                    if survey.partner_id.is_agency
                    else survey.partner_id.name
                )
            else:
                partner_name = ""
            survey.name_complete = f"{survey.name}.Phiếu khảo sát {partner_name}"

    @api.depends("per_retail_customer", "per_retail_taxi", "per_retail_fleet")
    def _compute_total_retail(self):
        for survey in self:
            survey.total_retail = (
                survey.per_retail_customer
                + survey.per_retail_taxi
                + survey.per_retail_fleet
            )

    @api.depends("per_wholesale_subdealer", "per_wholesale_garage")
    def _compute_total_wholesale(self):
        for survey in self:
            survey.total_wholesale = (
                survey.per_wholesale_subdealer + survey.per_wholesale_garage
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "SURVEY":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("mv.partner.survey.auto.ref")
                    or "SURVEY"
                )
        return super().create(vals_list)
