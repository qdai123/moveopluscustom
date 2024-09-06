# -*- coding: utf-8 -*-
import uuid

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

GROUP_SALES_MANAGER = "sales_team.group_sale_manager"
GROUP_SALES_ALL = "sales_team.group_sale_salesman_all_leads"
GROUP_SALESPERSON = "sales_team.group_sale_salesman"

BASE_SURVEY_STATEs = [
    ("draft", "Nháp"),
    ("progressing", "Đang khảo sát"),
    ("done", "Hoàn thành"),
    ("cancel", "Hủy"),
]

SHOPs_LIMITED = 5


class MvPartnerSurvey(models.Model):
    """Partner Survey for Moveo Plus"""

    _name = "mv.partner.survey"
    _description = _("Partner Survey")
    _inherit = ["mail.thread", "portal.mixin"]
    _order = "create_date desc"

    def _get_default_access_token(self):
        return str(uuid.uuid4())

    def _domain_brand_is_tire(self):
        brand_tire_id = self.env["mv.brand"].search(
            [("mv_brand_categ_id", "=", self.env.ref("mv_dms.brand_category_tire").id)],
            order="priority",
        )
        return [("brand_id", "in", brand_tire_id.ids)]

    def _domain_brand_is_lubricant(self):
        brand_tire_id = self.env["mv.brand"].search(
            [
                (
                    "mv_brand_categ_id",
                    "=",
                    self.env.ref("mv_dms.brand_category_lubricant").id,
                )
            ],
            order="priority",
        )
        return [("brand_id", "in", brand_tire_id.ids)]

    def _domain_brand_is_battery(self):
        brand_tire_id = self.env["mv.brand"].search(
            [
                (
                    "mv_brand_categ_id",
                    "=",
                    self.env.ref("mv_dms.brand_category_battery").id,
                )
            ],
            order="priority",
        )
        return [("brand_id", "in", brand_tire_id.ids)]

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
        domain="['|', ('parent_id.code', '=', 'SEA'), ('code', 'ilike', 'vn_')]",
        required=True,
        tracking=True,
        index=True,
    )
    shop_ids = fields.One2many(
        "mv.shop",
        "partner_survey_id",
        "Cửa hàng",
        domain=lambda self: [("partner_survey_id", "=", self.id)],
    )
    shop_count = fields.Integer(
        "Số cửa hàng cho phép tạo",
        compute="_compute_shop_limited",
    )
    brand_proportion_tire_ids = fields.One2many(
        "mv.brand.proportion",
        "partner_survey_id",
        "Tỷ trọng thương hiệu (Lốp)",
        domain=_domain_brand_is_tire,
        context={"default_is_tire": True},
    )
    brand_proportion_lubricant_ids = fields.One2many(
        "mv.brand.proportion",
        "partner_survey_id",
        "Tỷ trọng thương hiệu (Dầu nhớt)",
        domain=_domain_brand_is_lubricant,
        context={"default_is_lubricant": True},
    )
    brand_proportion_battery_ids = fields.One2many(
        "mv.brand.proportion",
        "partner_survey_id",
        "Tỷ trọng thương hiệu (Ắc quy)",
        domain=_domain_brand_is_battery,
        context={"default_is_battery": True},
    )
    total_quantity_brand_proportion_of_tire = fields.Float(
        "Tổng số lượng theo tỷ trọng thương hiệu (Lốp)",
        compute="_compute_total_quantity_brand_proportion",
        store=True,
        readonly=True,
    )
    total_quantity_brand_proportion_of_lubricant = fields.Float(
        "Tổng số lượng theo tỷ trọng thương hiệu (Dầu nhớt)",
        compute="_compute_total_quantity_brand_proportion",
        store=True,
        readonly=True,
    )
    total_quantity_brand_proportion_battery = fields.Float(
        "Tổng số lượng theo tỷ trọng thương hiệu (Ắc quy)",
        compute="_compute_total_quantity_brand_proportion",
        store=True,
        readonly=True,
    )
    service_detail_ids = fields.Many2many(
        "mv.service.detail",
        "mv_service_detail_partner_survey_rel",
        "service_detail_id",
        "partner_survey_id",
        "Sản phẩm dịch vụ",
    )
    mv_product_tire_ids = fields.One2many(
        "mv.product.product",
        "partner_survey_id",
        "TOP Sản phẩm (Lốp xe)",
        domain=_domain_brand_is_tire,
        context={"default_is_tire": True},
    )
    mv_product_lubricant_ids = fields.One2many(
        "mv.product.product",
        "partner_survey_id",
        "TOP Sản phẩm (Dầu nhớt)",
        domain=_domain_brand_is_lubricant,
        context={"default_is_lubricant": True},
    )
    mv_product_battery_ids = fields.One2many(
        "mv.product.product",
        "partner_survey_id",
        "TOP Sản phẩm (Ắc quy)",
        domain=_domain_brand_is_battery,
        context={"default_is_battery": True},
    )

    # === BASE Fields ===#
    access_token = fields.Char(
        "Access Token",
        default=lambda self: self._get_default_access_token(),
        copy=False,
    )
    active = fields.Boolean(default=True, tracking=True)
    create_date = fields.Datetime(
        "Ngày khảo sát",
        default=lambda self: fields.Datetime.now(),
        readonly=True,
    )
    create_uid = fields.Many2one(
        "res.users",
        "Người khảo sát",
        default=lambda self: self.env.user,
        readonly=True,
    )
    survey_date = fields.Date(
        "Ngày khảo sát",
        default=fields.Date.today,
        tracking=True,
    )
    survey_completed_date = fields.Date(
        "Ngày hoàn thành",
        readonly=True,
    )
    state = fields.Selection(
        BASE_SURVEY_STATEs,
        "Trạng thái",
        default="draft",
        readonly=True,
        index=True,
        tracking=True,
    )
    locked = fields.Boolean(
        default=False,
        copy=False,
        help="Không thể sửa đổi các Khảo Sát hoặc các thông tin đã khóa.",
    )
    name = fields.Char(
        "Phiếu khảo sát",
        default="SURVEY",
        copy=False,
        tracking=True,
    )
    owner = fields.Char(
        "Chủ sở hữu",
        required=True,
        tracking=True,
    )
    owner_phone = fields.Char(
        "Số điện thoại",
        size=32,
        tracking=True,
    )
    owner_email = fields.Char("Email", size=32)
    owner_dob = fields.Date(
        "Ngày sinh",
        tracking=True,
    )
    second_generation = fields.Char(
        "Thế hệ thứ 2",
        tracking=True,
    )
    second_generation_phone = fields.Char(
        "Số điện thoại",
        size=32,
        tracking=True,
    )
    second_generation_email = fields.Char("Email", size=32)
    second_generation_dob = fields.Date(
        "Ngày sinh",
        tracking=True,
    )
    relationship_with_owner = fields.Char(
        "Mối quan hệ",
        tracking=True,
    )
    number_of_years_business = fields.Float(
        "Số năm kinh doanh",
        default=0,
        digits=(10, 1),
        tracking=True,
    )
    proportion = fields.Float(
        "Tỷ trọng",
        default=1,
        tracking=True,
    )
    is_moveoplus_agency = fields.Boolean(
        "Đại lý Moveo Plus",
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
        "Khả năng tài chính",
        default="good",
        tracking=True,
    )
    # BÁN LẺ
    per_retail_customer = fields.Float("Khách hàng lẻ", default=0)
    per_retail_taxi = fields.Float("Taxi", default=0)
    per_retail_fleet = fields.Float("Công ty/Đội xe", default=0)
    total_retail = fields.Float(
        "Tổng số bán lẻ",
        compute="_compute_total_retail",
        store=True,
        readonly=True,
    )
    # BÁN BUÔN
    # per_wholesale_dealer = fields.Float("Đại lý cấp 1 (%)", default=0, tracking=True)
    per_wholesale_subdealer = fields.Float("Đại lý cấp 2", default=0)
    per_wholesale_garage = fields.Float("Garage", default=0)
    total_wholesale = fields.Float(
        "Tổng số bán buôn",
        compute="_compute_total_wholesale",
        store=True,
        readonly=True,
        tracking=True,
    )
    # DỊCH VỤ
    is_use_service = fields.Boolean(
        "Sử dụng dịch vụ",
        default=False,
        tracking=True,
    )
    proportion_service = fields.Float(
        "Tỷ trọng kinh doanh lốp so với dịch vụ khác", default=0
    )
    service_bay = fields.Integer("Số lượng cầu nâng", default=0)
    num_technicians = fields.Integer("Số lượng kỹ thuật viên", default=0)
    # num_sales = fields.Integer("Số lượng nhân viên bán hàng", default=0, tracking=True)
    num_administrative_staff = fields.Integer(
        "Số lượng nhân viên hành chính", default=0
    )

    # === RULES Fields ===#
    do_readonly = fields.Boolean("Readonly?", compute="_do_readonly")
    is_sales_manager = fields.Boolean(compute="_compute_permissions")

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "Mỗi một Phiếu khảo sát Đại lý phải là DUY NHẤT!",
        ),
        (
            "access_token_unique",
            "unique(access_token)",
            "Access token should be unique",
        ),
    ]

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

    @api.constrains("owner")
    def _check_owner_is_human(self):
        for survey in self:
            if survey.owner and len(survey.owner) < 3:
                raise UserError("Tên của CHỦ SỞ HỮU phải có ít nhất 3 ký tự!")

    @api.constrains("second_generation")
    def _check_second_generation_is_human(self):
        for survey in self:
            if survey.second_generation and len(survey.second_generation) < 3:
                raise UserError(
                    "Tên của NGƯỜI KẾ THỪA THẾ HỆ 2 phải có ít nhất 3 ký tự!"
                )

    @api.constrains("relationship_with_owner", "second_generation", "owner")
    def _check_relationship(self):
        for survey in self:
            if (
                survey.owner
                and survey.second_generation
                and not survey.relationship_with_owner
            ):
                raise UserError(
                    "Mối quan hệ người kế thừa thứ 2 và chủ sở hữu chưa rõ ràng!"
                )

    @api.constrains("survey_date")
    def _check_survey_date_is_not_in_future(self):
        for survey in self:
            if survey.survey_date > fields.Date.today():
                raise UserError("Ngày khảo sát không thể ở tương lai!")

    @api.constrains("partner_id", "survey_date")
    def _check_one_survey_one_partner_in_month(self):
        for survey in self:
            domain = [
                ("partner_id", "=", survey.partner_id.id),
                ("survey_date", ">", survey.survey_date.replace(day=1)),
                (
                    "survey_date",
                    "<",
                    survey.survey_date.replace(day=1) + relativedelta(months=1),
                ),
            ]
            if self.search_count(domain) > 1:
                raise UserError("Mỗi đại lý chỉ được khảo sát 1 lần trong tháng!")

    @api.constrains("shop_ids")
    def _check_shops_limited(self):
        for survey in self:
            if len(survey.shop_ids) > SHOPs_LIMITED:
                raise UserError(
                    "Không được phép vượt quá %s cửa hàng trên một phiếu khảo sát!"
                    % SHOPs_LIMITED
                )

    @api.constrains("total_retail", "total_wholesale")
    def _check_total_retail_wholesale(self):
        for survey in self:
            if survey.total_retail + survey.total_wholesale > 1:
                raise UserError("Tổng số bán lẻ và bán buôn không được vượt quá 100%!")

    @api.onchange("total_retail", "total_wholesale")
    def _onchange_total_retail_wholesale(self):
        if self.total_retail + self.total_wholesale > 1:
            raise UserError("Tổng số bán lẻ và bán buôn không được vượt quá 100%!")

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.name = "{}-SURVEY".format(self.partner_id.company_registry)

    @api.depends("partner_id")
    def _compute_is_partner_agency(self):
        for survey in self:
            survey.is_partner_agency = survey.partner_id.is_agency

    @api.depends("shop_ids")
    def _compute_shop_limited(self):
        for survey in self:
            survey.shop_count = len(survey.shop_ids)

    @api.depends(
        "brand_proportion_tire_ids",
        "brand_proportion_lubricant_ids",
        "brand_proportion_battery_ids",
    )
    def _compute_total_quantity_brand_proportion(self):
        for survey in self:
            survey.total_quantity_brand_proportion_of_tire = (
                self._calculate_total_quantity(survey.brand_proportion_tire_ids)
            )
            survey.total_quantity_brand_proportion_of_lubricant = (
                self._calculate_total_quantity(survey.brand_proportion_lubricant_ids)
            )
            survey.total_quantity_brand_proportion_battery = (
                self._calculate_total_quantity(survey.brand_proportion_battery_ids)
            )

    def _calculate_total_quantity(self, brand_proportion_ids):
        return sum(proportion.quantity_per_month for proportion in brand_proportion_ids)

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
                name_ref = self.env["ir.sequence"].next_by_code("survey.auto.ref")
                partner = self.env["res.partner"].browse(vals["partner_id"])
                vals["name"] = "{}-{}".format(partner.company_registry, name_ref)
        return super().create(vals_list)

    def unlink(self):
        for survey in self:
            if survey.state in ["done", "progressing"]:
                raise ValidationError(
                    "Không thể xóa Phiếu khảo sát đã hoàn thành hoặc đang khảo sát. "
                    "Vui lòng HỦY phiếu nếu "
                    + "Đang khảo sát"
                    + " rồi hãy thực hiện xóa phiếu!"
                )

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

    # === ACTION METHODS ===#

    def action_draft(self):
        surveys = self.filtered(lambda s: s.state in ["cancel", "progressing"])
        # TODO: Add more Wizard can clean up the data before Draft
        return surveys.write({"state": "draft"})

    def action_run(self):
        """
        Mark surveys as 'progressing' if they are in the 'draft' state.

        This method ensures that the survey can be marked as running by calling
        the `_can_be_running` method for each survey in the 'draft' state.

        :raises UserError: If any survey is not in the 'draft' state.
        :return: The number of records updated.
        :rtype: int
        """
        if any(survey.state != "draft" for survey in self):
            raise UserError("Phiếu phải ở trạng thái Nháp mới được khảo sát!")

        surveys = self.filtered(lambda s: s.state == "draft")
        for survey in surveys:
            survey._can_be_running()
        return surveys.write({"state": "progressing"})

    def action_complete(self):
        surveys = self.filtered(lambda s: s.state in ["progressing"])
        return surveys.write({"state": "done"})

    def action_cancel(self):
        """
        Cancel surveys if they are not in the 'done' state.

        This method checks if the cancellation is forced by a manager. If not, it iterates
        through the surveys and raises an error if any survey is in the 'done' state. Otherwise,
        it sets the state to 'cancel'.

        :raises UserError: If any survey is in the 'done' state and cancellation is not forced.
        :return: The number of records updated.
        :rtype: int
        """
        is_force_cancel = self.env.context.get(
            "force_cancel_by_manager", False
        ) and self.env.user.has_group(GROUP_SALES_MANAGER)
        if not is_force_cancel:
            surveys_to_cancel = self.filtered(lambda s: s.state != "done")
            if len(surveys_to_cancel) != len(self):
                raise UserError("Không thể hủy Phiếu khảo sát đã hoàn thành!")
            surveys_to_cancel.write({"state": "cancel"})
        else:
            self.write({"state": "cancel"})

    # === HELPER METHODS ===#

    def _can_be_running(self):
        """
        Check if the survey can be marked as running.

        This method ensures that there is no other survey in the 'progressing' state
        for the same partner within the same month.

        :raises ValidationError: If another survey is found in the 'progressing' state.
        :return: True if the survey can be marked as running.
        :rtype: bool
        """
        self.ensure_one()
        today = fields.Date.today()
        first_date_of_month = today.replace(day=1)
        last_date_of_month = first_date_of_month + relativedelta(months=1, days=-1)

        survey_progressing_in_month = self.env["mv.partner.survey"].search(
            [
                ("id", "!=", self.id),
                ("active", "=", True),
                ("state", "=", "progressing"),
                ("partner_id", "=", self.partner_id.id),
                "|",
                ("survey_date", ">=", first_date_of_month),
                ("survey_date", "<=", last_date_of_month),
            ],
            limit=1,
        )

        if survey_progressing_in_month:
            raise ValidationError(
                "Đại lý %s đã có phiếu đang khảo sát trong tháng này, mã phiếu là: %s"
                % (self.partner_id.short_name, survey_progressing_in_month.name)
            )

        return True

    def _prepare_completed_values(self):
        """
        Prepare the values to mark the survey as completed.

        This method sets the state to 'done' and updates the survey\_completed\_date
        to the current date.

        :return: A dictionary with the updated values.
        :rtype: dict
        """
        completed_values = {
            "state": "done",
            "survey_completed_date": fields.Date.today(),
        }
        _logger.info("Prepared completed values: %s", completed_values)
        return completed_values

    # === TOOLS METHODS ===#
