# -*- coding: utf-8 -*-
import uuid

from odoo import _, api, fields, models
from odoo.exceptions import UserError

GROUP_SALES_MANAGER = "sales_team.group_sale_manager"
GROUP_SALES_ALL = "sales_team.group_sale_salesman_all_leads"
GROUP_SALESPERSON = "sales_team.group_sale_salesman"


class MvPartnerSurvey(models.Model):
    _name = "mv.partner.survey"
    _description = _("Partner Survey")
    _inherit = ["mail.thread", "portal.mixin"]
    _order = "create_date desc"

    def _get_default_access_token(self):
        return str(uuid.uuid4())

    # === RULES Fields ===#
    def _do_readonly(self):
        """
        Set the `do_readonly` field based on the state of the record.

        This method iterates over each record and sets the `do_readonly` field to `True`
        if the state is "done", otherwise sets it to `False`.

        :return: False
        """
        for survey in self:
            survey.do_readonly = survey.state == "done"

    @api.depends_context("uid")
    def _compute_permissions(self):
        """
        Compute the permissions of the current user.

        This method computes the permissions of the current user and sets the `is_sales_manager`
        field to `True` if the user belongs to the "Sales Manager" group, otherwise sets it to `False`.

        :return: False
        """
        is_sales_manager = self.env.user.has_group(GROUP_SALES_MANAGER)
        self.is_sales_manager = is_sales_manager

    do_readonly = fields.Boolean("Readonly?", compute="_do_readonly")
    is_sales_manager = fields.Boolean(compute="_compute_permissions")

    # === RELATIONAL Fields ===#
    partner_id = fields.Many2one(
        "res.partner",
        "Đại lý",
        required=True,
        tracking=True,
        index=True,
    )
    is_partner_agency = fields.Boolean(
        compute="_compute_is_partner_agency",
        store=True,
        readonly=True,
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
        readonly=False,
        default=lambda self: self.env.company.currency_id,
    )
    region_id = fields.Many2one(
        "mv.region",
        "Khu vực",
        domain="[('type', 'in', ['region', 'subregion'])]",
        required=True,
        tracking=True,
        index=True,
    )
    shop_ids = fields.One2many(
        "mv.shop",
        "partner_survey_id",
        "Cửa hàng",
        domain=lambda self: [("partner_survey_id", "=", self.id)],
        required=True,
    )
    brand_proportion_ids = fields.One2many(
        "mv.brand.proportion",
        "partner_survey_id",
        "Tỷ trọng thương hiệu",
        domain=lambda self: [("partner_survey_id", "=", self.id)],
        required=True,
    )
    service_detail_ids = fields.One2many(
        "mv.service.detail",
        "partner_survey_id",
        "Dịch vụ",
        domain=lambda self: [("partner_survey_id", "=", self.id)],
        required=True,
    )
    mv_product_ids = fields.Many2many(
        "mv.product.product",
        "mv_product_partner_survey_rel",
        "mv_product_id",
        "partner_survey_id",
        domain="[('product_type', 'in',  ['size_lop'])]",
        string="TOP Sản phẩm (Size Lốp)",
    )
    mv_product_lubricant_ids = fields.Many2many(
        "mv.product.product",
        "mv_product_lubricant_partner_survey_rel",
        "mv_product_id",
        "partner_survey_id",
        domain="[('product_type', 'in',  ['lubricant'])]",
        string="TOP Sản phẩm (Dầu nhớt)",
    )

    # === BASE Fields ===#
    access_token = fields.Char(
        "Access Token",
        default=lambda self: self._get_default_access_token(),
        copy=False,
    )
    active = fields.Boolean(default=True, tracking=True)
    create_date = fields.Datetime(
        "Ngày khảo sát", default=lambda self: fields.Datetime.now()
    )
    create_uid = fields.Many2one(
        "res.users", "Người khảo sát", default=lambda self: self.env.user
    )
    survey_date = fields.Date("Ngày khảo sát", default=fields.Date.today, tracking=True)
    state = fields.Selection(
        [("draft", "Khảo sát"), ("done", "Hoàn thành"), ("cancel", "Hủy")],
        default="draft",
        string="Trạng thái",
        tracking=True,
    )
    name = fields.Char("Phiếu khảo sát", default="SURVEY", tracking=True)
    owner = fields.Char("Chủ sở hữu", required=True, tracking=True)
    second_generation = fields.Char("Thế hệ thứ 2", required=True, tracking=True)
    number_of_years_bussiness = fields.Float(
        "Số năm kinh doanh",
        default=0,
        digits=(10, 1),
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
        "Đại lý của Moveo Plus",
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
    per_retail_customer = fields.Float("Khách hàng lẻ", default=0, tracking=True)
    per_retail_taxi = fields.Float("Taxi", default=0, tracking=True)
    per_retail_fleet = fields.Float("Công ty/Đội xe", default=0, tracking=True)
    total_retail = fields.Float(
        "Tổng số bán lẻ",
        compute="_compute_total_retail",
        store=True,
        readonly=True,
        tracking=True,
    )
    # BÁN BUÔN
    total_wholesale = fields.Float(
        "Tổng số bán buôn",
        compute="_compute_total_wholesale",
        store=True,
        readonly=True,
        tracking=True,
    )
    # per_wholesale_dealer = fields.Float("Đại lý cấp 1 (%)", default=0, tracking=True)
    per_wholesale_subdealer = fields.Float("Đại lý cấp 2", default=0, tracking=True)
    per_wholesale_garage = fields.Float("Garage", default=0, tracking=True)
    # DỊCH VỤ
    is_use_service = fields.Boolean("Sử dụng dịch vụ", default=False, tracking=True)
    proportion_service = fields.Float(
        "Tỷ trọng kinh doanh lốp so với dịch vụ khác", default=0, tracking=True
    )
    service_bay = fields.Integer("Số lượng cầu nâng", default=0, tracking=True)
    num_technicians = fields.Integer("Số lượng kỹ thuật viên", default=0, tracking=True)
    # num_sales = fields.Integer("Số lượng nhân viên bán hàng", default=0, tracking=True)
    num_administrative_staff = fields.Integer(
        "Số lượng nhân viên hành chính", default=0, tracking=True
    )

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "Mỗi một Phiếu khảo sát Đối tác phải là DUY NHẤT!",
        ),
        (
            "access_token_unique",
            "unique(access_token)",
            "Access token should be unique",
        ),
    ]

    @api.constrains("owner")
    def _check_owner_is_human(self):
        for survey in self:
            if survey.owner and len(survey.owner) < 3:
                raise UserError("Chủ sở hữu phải có ít nhất 3 ký tự!")

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.name = "{}-SURVEY".format(self.partner_id.company_registry)

    @api.depends("partner_id")
    def _compute_is_partner_agency(self):
        for survey in self:
            survey.is_partner_agency = survey.partner_id.is_agency

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
            if vals.get("partner_id"):
                name_ref = self.env["ir.sequence"].next_by_code(
                    "mv.partner.survey.auto.ref"
                )
                partner = self.env["res.partner"].browse(vals["partner_id"])
                vals["name"] = "{}-{}".format(partner.company_registry, name_ref)
        return super().create(vals_list)

    def unlink(self):
        for survey in self:
            if survey.state == "done":
                raise UserError("Không thể xóa Phiếu khảo sát đã hoàn thành!")

        related_records = [
            self.with_context(force_delete=True).shop_ids,
            self.with_context(force_delete=True).brand_proportion_ids,
            self.with_context(force_delete=True).service_detail_ids,
            self.with_context(force_delete=True).mv_product_ids,
        ]

        res = super().unlink()

        for records in related_records:
            records.unlink()

        return res

    def action_complete(self):
        for survey in self:
            if survey.state == "draft":
                survey.state = "done"

    def action_cancel(self):
        force_cancel = self.env.context.get(
            "force_cancel_by_manager", False
        ) and self.env.user.has_group(GROUP_SALES_MANAGER)
        if not force_cancel:
            for survey in self:
                if survey.state == "done":
                    raise UserError("Không thể hủy Phiếu khảo sát đã hoàn thành!")
                survey.state = "cancel"
        else:
            self.write({"state": "cancel"})

    # === TOOLS ===#
