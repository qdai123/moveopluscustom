# -*- coding: utf-8 -*-
import logging
import re
from datetime import datetime

import pytz

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# Date format used in the module
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Access Groups
HELPDESK_USER = "helpdesk.group_helpdesk_user"
HELPDESK_MANAGER = "helpdesk.group_helpdesk_manager"

# Ticket Type Codes for Warranty Activation
SUB_DEALER_CODE = "kich_hoat_bao_hanh_dai_ly"
END_USER_CODE = "kich_hoat_bao_hanh_nguoi_dung_cuoi"

NEW_STATE = "mv_website_helpdesk.warranty_stage_new"
NOT_ASSIGNED_ERROR = (
    "You are not assigned to the ticket or don't have sufficient permissions!"
)
NOT_NEW_STATE_ERROR = "You can only delete a ticket when it is in 'New' state."

# Error Codes
IS_EMPTY = "is_empty"
CODE_NOT_FOUND = "code_not_found"
CODE_ALREADY_REGISTERED = "code_already_registered"


class HelpdeskTicket(models.Model):
    _inherit = "helpdesk.ticket"

    tag_ids = fields.Many2many(tracking=True)
    partner_phone = fields.Char(tracking=True)
    partner_email = fields.Char(tracking=True)
    @api.depends_context("uid")
    def _is_helpdesk_manager(self):
        """Compute if the current user is a helpdesk manager."""
        for ticket in self:
            ticket.is_helpdesk_manager = self.env.user.has_group(HELPDESK_MANAGER)

    @api.depends("partner_id", "ticket_type_id")
    def _compute_name(self):
        """Compute the name of the ticket based on partner and ticket type."""
        for ticket in self:
            partner_name = ticket.partner_id.name.upper() if ticket.partner_id else "-"
            ticket_type_name = (
                ticket.ticket_type_id.name if ticket.ticket_type_id else "-"
            )

            now_utc = datetime.utcnow()
            now_user = now_utc.astimezone(pytz.timezone(ticket.partner_id.tz or "UTC"))
            lang = self.env["res.lang"]._lang_get(
                ticket.partner_id.lang or self.env.user.lang
            )
            date_format = lang.date_format
            time_format = lang.time_format
            formatted_date = now_user.strftime(date_format + " " + time_format)

            ticket.name = f"{partner_name}/{ticket_type_name}({formatted_date})"

    # === ACCESS / RULE Fields ===#
    is_helpdesk_manager = fields.Boolean("Manager", compute="_is_helpdesk_manager")
    # === INHERIT Fields ===#
    name = fields.Char(compute="_compute_name", store=True, required=False)
    # === ADDITIONAL Fields ===#
    portal_lot_serial_number = fields.Text("Nhập số serial")
    ticket_update_date = fields.Datetime(
        "Ngày cập nhật",
        default=lambda self: fields.Datetime.now(),
        readonly=True,
    )
    helpdesk_ticket_product_move_ids = fields.One2many(
        comodel_name="mv.helpdesk.ticket.product.moves",
        inverse_name="helpdesk_ticket_id",
        string="Lot/Serial Number",
        help="For Activation Warranty Ticket",
    )
    helpdesk_warranty_ticket_ids = fields.One2many(
        comodel_name="mv.helpdesk.ticket.product.moves",
        inverse_name="mv_warranty_ticket_id",
        string="Lot/Serial Number",
        help="For Claim Warranty Ticket",
    )
    # === SUB-DEALER Ticket Type ===#
    is_sub_dealer = fields.Boolean(compute="_compute_ticket_type")
    sub_dealer_name = fields.Char("Sub-Dealer")
    # === END-USER Ticket Type ===#
    is_end_user = fields.Boolean(compute="_compute_ticket_type")
    tel_activation = fields.Char("Số điện thoại")
    license_plates = fields.Char("Biển số xe")
    mileage = fields.Integer("Số Km", default=0)
    mv_is_warranty_ticket = fields.Boolean(compute="compute_is_warranty_ticket")
    invalid_serials = fields.Text("Số serial chưa kích hoạt")
    claim_warranty_ids = fields.Many2many(
        "mv.helpdesk.ticket.product.moves",
        "claim_ticket_product_moves_relation",
        "claim_ticket_id",
        "move_id",
        string="Sản phẩm yêu cầu bảo hành",
        domain="[('stock_lot_id', '!=', False)]",
    )
    can_be_create_order = fields.Boolean(readonly=True)

    @api.onchange("claim_warranty_ids")
    def onchange_can_be_create_order(self):
        for ticket in self:
            approved_claim = ticket.claim_warranty_ids.filtered(
                lambda claim: claim.is_claim_warranty_approved
            )
            all_claim = ticket.claim_warranty_ids
            if len(all_claim) == len(approved_claim):
                ticket.write({"can_be_create_order": True})
            else:
                ticket.write({"can_be_create_order": False})

    @api.onchange("claim_warranty_ids")
    def onchange_claim_warranty_ids(self):
        for rec in self:
            if rec.claim_warranty_ids:
                rec.helpdesk_warranty_ticket_ids = [(6, 0, rec.claim_warranty_ids.ids)]

    @api.depends("team_id")
    def compute_is_warranty_ticket(self):
        for move in self:
            move.mv_is_warranty_ticket = False
            ticket_ref = self.env.ref(
                "mv_website_helpdesk.mv_helpdesk_claim_warranty",
                raise_if_not_found=False,
            )
            if move.team_id.id == ticket_ref.id and ticket_ref and move.team_id:
                move.mv_is_warranty_ticket = True

    # ==================================
    # ORM Methods
    # ==================================

    @api.depends("ticket_type_id")
    def _compute_ticket_type(self):
        """Compute the ticket type based on the ticket_type_id's code."""
        for ticket in self:
            if ticket.ticket_type_id:
                ticket.is_sub_dealer = ticket.ticket_type_id.code == SUB_DEALER_CODE
                ticket.is_end_user = ticket.ticket_type_id.code == END_USER_CODE
            else:
                ticket.is_sub_dealer = False
                ticket.is_end_user = False

    def _check_codes_already_exist(self):
        """Check if the codes already exist in the system."""
        for ticket in self:
            codes = (
                ticket.portal_lot_serial_number
                if isinstance(ticket.portal_lot_serial_number, list)
                else self._format_portal_lot_serial_number(
                    ticket.portal_lot_serial_number
                )
            )
            # Get all lot names and QR codes from helpdesk_ticket_product_move_ids
            lot_names = set(ticket.helpdesk_ticket_product_move_ids.mapped("lot_name"))
            qr_codes = set(ticket.helpdesk_ticket_product_move_ids.mapped("qr_code"))
            # Check if any code already exists
            existing_codes = lot_names.union(qr_codes)
            conflicting_codes = [code for code in codes if code in existing_codes]
            if conflicting_codes:
                raise ValidationError(
                    f"The following codes are already registered "
                    f"for this ticket: {', '.join(conflicting_codes)}. Please select different codes."
                )

    # ==================================
    # CRUD Methods
    # ==================================

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "partner_email" in vals and "partner_name" in vals:
                partner = (
                    self.env["res.partner"]
                    .sudo()
                    .search(
                        [
                            ("name", "=", vals["partner_name"]),
                            ("email", "=", vals["partner_email"]),
                        ],
                        limit=1,
                    )
                )
                if (
                        partner
                        and not partner.is_agency
                        and not partner.parent_id.is_agency
                ):
                    raise ValidationError(
                        "Bạn không phải là Đại lý của Moveo Plus. "
                        "Vui lòng liên hệ bộ phận hỗ trợ để đăng ký thông tin."
                    )
                vals["partner_id"] = partner.id
        tickets = super(HelpdeskTicket, self).create(vals_list)

        for ticket in tickets:
            if ticket.ticket_type_id and ticket.ticket_type_id.code in [
                SUB_DEALER_CODE,
                END_USER_CODE,
            ]:
                self._process_ticket(ticket, vals_list)

        return tickets

    def write(self, vals):
        if vals:
            vals["ticket_update_date"] = fields.Datetime.now()
        return super(HelpdeskTicket, self).write(vals)

    def unlink(self):
        not_system_user = not (self.env.is_admin() or self.env.is_superuser())
        is_not_manager = self.env.user.has_group(HELPDESK_MANAGER)

        for ticket in self:
            not_assigned_to_user = ticket.user_id != self.env.user

            if not_system_user and is_not_manager and not_assigned_to_user:
                raise AccessError(_(NOT_ASSIGNED_ERROR))
            elif (
                    not_system_user
                    and is_not_manager
                    and ticket.stage_id.id != self.env.ref(NEW_STATE).id
            ):
                raise ValidationError(_(NOT_NEW_STATE_ERROR))

            # Unlink all related ticket product moves
            ticket.helpdesk_ticket_product_move_ids.unlink()

        return super(HelpdeskTicket, self).unlink()

    # ==================================
    # BUSINESS Methods
    # ==================================

    @staticmethod
    def convert_to_list_codes(codes):
        """
        Convert the input codes into a list of codes.
        - If the input is a string, extract numbers using regex.
        - If the input is already a list, use it directly.
        """
        if isinstance(codes, str):
            return re.findall(r"\b\d+\b", codes)
        elif isinstance(codes, list):
            return [str(code) for code in codes if isinstance(code, (int, str))]
        return []

    def _process_ticket(self, ticket, vals_list):
        for vals in vals_list:
            if vals.get("name") == "new":
                ticket._compute_name()

            codes = vals["portal_lot_serial_number"]
            if codes:
                ticket_type = ticket.ticket_type_id
                self._process_ticket_product_moves(ticket, ticket_type, codes)

        ticket.clean_data()

    def _process_ticket_product_moves(self, ticket, ticket_type, codes):
        product_lots_ids = self._scanning(ticket, ticket_type, codes)
        for stock in self.env["stock.lot"].browse(product_lots_ids):
            self._registering_ticket_product(ticket, ticket_type, stock)

    def _scanning(self, ticket, ticket_type, codes):
        if not codes:
            raise ValidationError("Vui lòng nhập hoặc quét mã để quá trình tiếp tục.")

        # Convert to list of unique codes
        unique_codes = list(set(self.convert_to_list_codes(codes)))

        # Prepare validated data and collect error messages
        res_data, error_messages = self._prepare_validated_data(
            ticket, ticket_type, unique_codes
        )

        # Filter and raise validation errors if any exist
        if error_messages:
            filtered_errors = [
                err_msg[1]
                for err_msg in error_messages
                if err_msg[0] in {IS_EMPTY, CODE_NOT_FOUND, CODE_ALREADY_REGISTERED}
            ]
            if filtered_errors:
                raise ValidationError("\n".join(filtered_errors))

        return res_data

    def _registering_ticket_product(self, ticket, ticket_type, stock):
        ticket_product_env = self.env["mv.helpdesk.ticket.product.moves"].sudo()
        existing_product_unregistered = ticket_product_env.search(
            [("helpdesk_ticket_id", "=", False), ("stock_lot_id", "=", stock.id)],
            limit=1,
        )
        if existing_product_unregistered:
            existing_product_unregistered.unlink()

        ticket_product_data = {
            "helpdesk_ticket_id": ticket.id,
            "stock_lot_id": stock.id,
            "customer_date_activation": fields.Date.today(),
        }

        if ticket_type.code == END_USER_CODE:
            ticket_product_data.update(
                {
                    "customer_phone_activation": ticket.tel_activation,
                    "customer_license_plates_activation": ticket.license_plates,
                    "customer_mileage_activation": ticket.mileage,
                }
            )

        ticket_product_env.create(ticket_product_data)

    def _prepare_validated_data(self, ticket, ticket_type, codes):
        results = set()
        error_messages = []

        # [!] ===== Validate empty codes =====
        if not codes:
            message_err = "Vui lòng nhập vào Số lô/Mã vạch hoặc mã QR-Code để kiểm tra!"
            error_messages.append((IS_EMPTY, message_err))

        validated_qr_code = self._validate_qr_code(codes)
        validated_lot_serial_number = self._validate_lot_serial_number(codes)

        # [!] ===== Validate codes are not found on system =====
        if not validated_qr_code and not validated_lot_serial_number:
            message_err = (
                f"Mã {', '.join(codes) if len(codes) > 1 else codes[0]} "
                f"không tồn tại trên hệ thống hoặc chưa cập nhật.",
            )
            error_messages.append((CODE_NOT_FOUND, message_err))

        # [!] ===== Validate codes has been registered on other tickets =====
        qr_codes = list(set(validated_qr_code.mapped("ref")))
        lot_serial_numbers = list(set(validated_lot_serial_number.mapped("name")))

        # QR-Codes VALIDATION
        if qr_codes:
            self._validate_codes(
                error_messages=error_messages,
                field_name="ref",
                codes=qr_codes,
                ticket_type=ticket_type,
                partner=ticket.partner_id,
            )

        # Lot/Serial Number VALIDATION
        if lot_serial_numbers:
            self._validate_codes(
                error_messages=error_messages,
                field_name="name",
                codes=lot_serial_numbers,
                ticket_type=ticket_type,
                partner=ticket.partner_id,
            )

        # Merge the results and remove duplicates by using a set
        results.update(validated_qr_code.ids)
        results.update(validated_lot_serial_number.ids)

        # Convert the set back to a list
        results = list(results)
        error_messages = list(set(error_messages))

        return results, error_messages

    def _validate_qr_code(self, codes):
        """
        Validate the input codes against existing QR codes.
        - If the input is a string, split it into a list of codes.
        - If the input is already a list, use it directly.
        - Return a list of validated QR codes.

        Args:
            codes (str or list): Input QR codes as a comma-separated string or list.

        Returns:
            recordset: A recordset of `stock.lot` matching the validated QR codes.
        """
        valid_codes = []

        if isinstance(codes, str):
            # Split string into a list of codes, stripping whitespace
            valid_codes = [code.strip() for code in codes.split(",") if code.strip()]
        elif isinstance(codes, list):
            # Ensure all elements are strings
            valid_codes = [str(code) for code in codes if isinstance(code, (int, str))]

        product_lots = self.env["stock.lot"].search(
            [("ref", "in", valid_codes), ("inventory_period_id", "!=", False)],
            order="ref desc",
        )
        return product_lots or self.env["stock.lot"]

    def _validate_lot_serial_number(self, codes):
        """ "
        Validate the input codes against existing Serial Number codes.
        - If the input is a string, split it into a list of codes.
        - If the input is already a list, use it directly.
        - Return a list of validated Serial Number codes.

        Args:
            codes (str or list): Input Serial Number codes as a comma-separated string or list.

        Returns:
            recordset: A recordset of `stock.lot` matching the validated Serial Number codes.
        """
        valid_codes = []

        if isinstance(codes, str):
            # Split string into a list of codes, stripping whitespace
            valid_codes = [code.strip() for code in codes.split(",") if code.strip()]
        elif isinstance(codes, list):
            # Ensure all elements are strings
            valid_codes = [str(code) for code in codes if isinstance(code, (int, str))]

        product_lots = self.env["stock.lot"].search([("name", "in", valid_codes)])
        return product_lots or self.env["stock.lot"]

    def _validate_codes(self, error_messages, field_name, **kwargs):
        model_search = "mv.helpdesk.ticket.product.moves"
        codes = kwargs.get("codes")
        ticketType = kwargs.get("ticket_type")
        partner = kwargs.get("partner")

        for code in codes:
            domain_sub_dealer = self._get_domain(SUB_DEALER_CODE, code, field_name)
            conflicting_ticket_sub_dealer = (
                self.env[model_search].sudo().search(domain_sub_dealer, limit=1)
            )

            domain_end_user = self._get_domain(END_USER_CODE, code, field_name)
            conflicting_ticket_end_user = (
                self.env[model_search].sudo().search(domain_end_user, limit=1)
            )

            if (
                    len(conflicting_ticket_sub_dealer) > 0
                    and len(conflicting_ticket_end_user) > 0
            ):
                message_err = (
                    f"Mã {code} đã trùng với Tickets khác có mã là "
                    f"(#{conflicting_ticket_sub_dealer.helpdesk_ticket_id.id}, "
                    f"#{conflicting_ticket_end_user.helpdesk_ticket_id.id})."
                )
                error_messages.append((CODE_ALREADY_REGISTERED, message_err))
            else:
                if ticketType.code in [SUB_DEALER_CODE, END_USER_CODE]:
                    self._handle_code(
                        conflicting_ticket_sub_dealer=conflicting_ticket_sub_dealer,
                        conflicting_ticket_end_user=conflicting_ticket_end_user,
                        code=code,
                        partner=partner,
                        error_messages=error_messages,
                        ticket_type_code=ticketType.code,
                    )

    def _get_domain(self, ticket_type_code, code, field_name):
        return [
            ("helpdesk_ticket_type_id.code", "=", ticket_type_code),
            (f"stock_lot_id.{field_name}", "=", code),
            "|",
            ("helpdesk_ticket_id", "!=", False),
            ("mv_warranty_ticket_id", "!=", False),
        ]

    def _handle_code(self, **kwargs):
        conflicting_ticket_sub_dealer = kwargs.get("conflicting_ticket_sub_dealer")
        conflicting_ticket_end_user = kwargs.get("conflicting_ticket_end_user")
        code = kwargs.get("code")
        partner = kwargs.get("partner")
        error_messages = kwargs.get("error_messages")
        ticket_type_code = kwargs.get("ticket_type_code")

        validate_different_partner_for_sub = (
                len(conflicting_ticket_sub_dealer) > 0
                and conflicting_ticket_sub_dealer.partner_id
                and conflicting_ticket_sub_dealer.partner_id.id != partner.id
        )
        validate_different_partner_for_end = (
                len(conflicting_ticket_end_user) > 0
                and conflicting_ticket_end_user.partner_id
                and conflicting_ticket_end_user.partner_id.id != partner.id
        )
        validate_same_partner_for_sub = (
                len(conflicting_ticket_sub_dealer) > 0
                and conflicting_ticket_sub_dealer.partner_id
                and conflicting_ticket_sub_dealer.partner_id.id == partner.id
        )
        validate_same_partner_for_end = (
                len(conflicting_ticket_end_user) > 0
                and conflicting_ticket_end_user.partner_id
                and conflicting_ticket_end_user.partner_id.id == partner.id
        )
        # Validate if the code is already registered on other tickets by different Partners
        if validate_different_partner_for_sub or validate_different_partner_for_end:
            conflicting_ticket = (
                conflicting_ticket_sub_dealer
                if validate_different_partner_for_sub
                else conflicting_ticket_end_user
            )
            message_err = (
                f"Mã {code} đã được đăng ký cho đơn vị khác, "
                f"phiếu có mã là (#{conflicting_ticket.helpdesk_ticket_id.id})."
            )
            error_messages.append((CODE_ALREADY_REGISTERED, message_err))
        # Validate if the code is already registered on other tickets by same Partners
        elif validate_same_partner_for_sub or validate_same_partner_for_end:
            conflicting_ticket = (
                conflicting_ticket_sub_dealer
                if validate_same_partner_for_sub
                else conflicting_ticket_end_user
            )
            message_err = (
                f"Mã {code} đã được đăng ký cho đơn vị khác, "
                f"phiếu có mã là (#{conflicting_ticket.helpdesk_ticket_id.id})."
            )
            error_messages.append((CODE_ALREADY_REGISTERED, message_err))
        # Validate if the code is already registered on other tickets with specific ticket type by current Partner
        else:
            if (
                    ticket_type_code == SUB_DEALER_CODE
                    and len(conflicting_ticket_end_user) > 0
            ):
                message_err = (
                    f"Mã {code} đã trùng với Ticket khác, "
                    f"phiếu có mã là (#{conflicting_ticket_end_user.helpdesk_ticket_id.id})."
                )
                error_messages.append((CODE_ALREADY_REGISTERED, message_err))
            elif (
                    ticket_type_code == END_USER_CODE
                    and len(conflicting_ticket_end_user) > 0
            ):
                message_err = (
                    f"Mã {code} đã trùng với Ticket khác, "
                    f"phiếu có mã là (#{conflicting_ticket_end_user.helpdesk_ticket_id.id})."
                )
                error_messages.append((CODE_ALREADY_REGISTERED, message_err))

    def clean_data(self):
        self.write({"portal_lot_serial_number": ""})

    # ==================================
    # ACTION / BUTTON / WIZARD Methods
    # ==================================

    def action_wizard_import_lot_serial_number(self):
        """Open the wizard to import lot/serial number or QR-Code."""
        self.ensure_one()

        view_id = self.env.ref(
            "mv_helpdesk.mv_helpdesk_wizard_import_lot_serial_number_form_view",
            raise_if_not_found=False,
        )
        if not view_id:
            raise UserError(_("The form view for the wizard is not available."))

        context = dict(self.env.context)
        context.update(
            {
                "default_helpdesk_ticket_id": self.id,
                "default_helpdesk_ticket_type_id": (
                    self.ticket_type_id.id if self.ticket_type_id else None
                ),
            }
        )

        return {
            "name": _("Import Lot/Serial Number or QR-Code"),
            "type": "ir.actions.act_window",
            "res_model": "wizard.import.lot.serial.number",
            "view_mode": "form",
            "view_id": view_id.id,
            "context": context,
            "target": "new",
        }

    def action_generate_sale_order(self):
        self.ensure_one()
        products = self.helpdesk_warranty_ticket_ids.mapped("product_id")
        product_tmps = products.mapped("product_tmpl_id")
        order = self.env["sale.order"].create(
            {
                "is_claim_warranty": True,
                "mv_moves_warranty_ids": [
                    (6, 0, self.helpdesk_warranty_ticket_ids.ids)
                ],
                "state": "draft",
                "partner_id": self.partner_id.id,
                "partner_invoice_id": self.partner_id.id,
                "partner_shipping_id": self.partner_id.id,
                "team_id": self.env.ref(
                    "sales_team.team_sales_department", raise_if_not_found=False
                ).id,
            }
        )
        if order:
            for product in product_tmps:
                order_line = self.env["sale.order.line"].create(
                    {
                        "display_type": False,
                        "order_id": order.id,
                        "product_template_id": product.id,
                        "product_id": self.env["product.product"]
                        .search([("product_tmpl_id", "=", product.id)], limit=1)
                        .id,
                        "product_uom_qty": 1.0,
                        "product_uom": product.uom_id.id,
                        "price_unit": product.list_price,
                        "tax_id": [(6, 0, product.taxes_id.ids)],
                        "name": (
                            product.name + product.description_sale
                            if product.name and product.description_sale
                            else ""
                        ),
                    }
                )
            return {
                "name": _("Tạo đơn bán"),
                "type": "ir.actions.act_window",
                "res_model": "sale.order",
                "view_mode": "form",
                "view_id": self.env.ref("sale.view_order_form").id,
                "context": {"create_order_from_claim_ticket": True},
                "res_id": order.id,
                "domain": [("id", "=", order.id)],
                "target": "new",
            }
