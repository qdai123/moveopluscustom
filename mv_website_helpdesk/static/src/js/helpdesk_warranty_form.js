/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import { Component, useState } from "@odoo/owl";
import publicWidget from "@web/legacy/js/public/public_widget";
import {ScannerDialog} from "../components/scanner_dialog/scanner_dialog";

const ERROR_MESSAGES = {
    EMPTY_REQUIRED_FIELDS: "Vui lòng nhập vào đủ thông tin yêu cầu!",
    EMPTY_PHONE_NUMBER: "Vui lòng nhập số điện thoại của bạn.",
    INVALID_PHONE_PATTERN: "Số điện thoại không hợp lệ. Vui lòng nhập số có 10 chữ số.",
    INVALID_PHONE_NUMBER: "Số điện thoại không hợp lệ.",
    PARTNER_NOT_FOUND: "Không tìm thấy thông tin theo số điện thoại của bạn hoặc bạn không phải là Đại lý của Moveo Plus.\n\n Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin."
};

/**
 * Helpdesk Warranty Form Widget
 */
publicWidget.registry.HelpdeskWarrantyForm = publicWidget.Widget.extend({
    selector: "form[name='activation_warranty_form'], form[name='claim_warranty_form']",
    events: {
        "click #scanning-btn": "openScannerDialog",
        "click #search-btn": "_onSearchButton",
        "click #submit-activation-warranty": "_onSubmitActivationButton",
        "click #submit-claim-warranty": "_onSubmitClaimButton",
    },
    
    /**
     * @constructor
     * @param {Object} parent
     */
    init() {
        this._super(...arguments);
        this._initializeServices();
        this.canSubmitTicket = true;
    },

    /**
     * @override
     * @returns {Promise}
     */
    async willStart() {
        // Check if the form is 'claim_warranty_form'
        this.isClaimWarrantyForm = this.$target.closest("form[name='claim_warranty_form']").length > 0;
        if (this.isClaimWarrantyForm) {
            this._populateFormFromCookies();
            this._clearCookies();
        }
        return Promise.all([this._super()]);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------
    
    /**
     * Opens the Scanner Dialog
     */
    openScannerDialog() {
        try {
            this.dialogService.add(ScannerDialog, {
                body: _t("Please, scanning your Serial Number here!"),
                onBarcodeScanned: async (scannedCode) => scannedCode ? scannedCode.trim() : "",
                confirm: (codes) => {
                    const SerialNums = document.getElementById("helpdesk_warranty_input_portal_lot_serial_number");
                    codes.forEach(code => {
                        if (!SerialNums.value.includes(code)) {
                            SerialNums.value += `${code},`;
                        }
                    });
                },
                cancel: () => {},
            });
        } catch (e) {
            console.error("Failed to open scanner dialog: ", e);
        }
    },
    
    /**
     * Handles the search button click event.
     * It validates the phone number and fetches the partner's information.
     *
     * @param {Event} ev - The click event.
     */
    async _onSearchButton(ev) {
        const $searchButton = $(ev.currentTarget);
        const $phoneNumber = $("#o_website_helpdesk_search_phone_number");
        const $errorMessage = $("#phonenumber-error-message");
        // Validate the phone number
        if (!this._validatePhoneNumber($phoneNumber.val(), $errorMessage)) {
            return;
        }
        // Fetch the partner's information
        await this._fetchPartnerInfo($phoneNumber.val(), $errorMessage);
    },
    
    /**
     * Handles the submit button click event on Claim Warranty Form.
     * @private
     * @param {Event} ev
     */
    async _onSubmitClaimButton(ev) {
        ev.preventDefault();

        const $ticketType = $("#helpdesk_warranty_select_ticket_type_id");
        const ticketTypeObj = await this._fetchClaimTicket($ticketType.val());

        const $partnerName = $("#helpdeskWarrantyInputPartnerName");
        const $partnerEmail = $("#helpdeskWarrantyInputPartnerEmail");
        const $portalLotSerialNumber = $("#helpdesk_warranty_input_portal_lot_serial_number");

        const phonePattern = /^[0-9]{10}$/; // Only digits, exactly 10 characters
        const $telNumberActivation = $("#helpdesk_warranty_input_tel_activation");
         if ($telNumberActivation.val() && !phonePattern.test($telNumberActivation.val())) {
            console.error("Errors: ", ERROR_MESSAGES.INVALID_PHONE_PATTERN);
            this.notification.add(
                ERROR_MESSAGES.INVALID_PHONE_PATTERN,
                { type: "warning" }
            );
            this.canSubmitTicket = false;
        }

        const $warrantyAttachments = $('#warranty_attachments');
        const is_attachment_empty = !$warrantyAttachments.length || !$warrantyAttachments[0].files.length;
        if (is_attachment_empty) {
            $warrantyAttachments.attr("required", true).addClass("border-danger");
            this.notification.add("Vui lòng đính kèm thêm tài liệu, hình ảnh để bảo hành!", {
                type: "warning",
            });
            this.canSubmitTicket = false;
        } else {
            $warrantyAttachments.attr('required', false);
        }

        if (ticketTypeObj && ticketTypeObj[0] && ticketTypeObj[0].code == "yeu_cau_bao_hanh") {
            const fileBlockEl = document.querySelector(".o_file_block");
            if (!fileBlockEl && is_attachment_empty) {
                this.notification.add(ERROR_MESSAGES.EMPTY_REQUIRED_FIELDS, {
                    type: "danger",
                });
                this.canSubmitTicket = false;
                //this._setCookie();
                //return setInterval(this.returnClaimWarranty, 6000);
            }
        }

        let tel_activation = null
        if ($telNumberActivation.val() == null) {
            const domain = ['|', ['email', '=', $partnerEmail.val()], ['name', '=', $partnerName.val()]];
            const res = await this.orm.searchRead("res.partner", domain, ['name', 'email', 'phone', 'mobile'], {
                limit: 1,
            });
            if (res[0].phone) {
                tel_activation = res[0].phone
            } else if (res[0].mobile) {
                tel_activation = res[0].mobile
            }
        }

        // Check scanned codes
        if ($portalLotSerialNumber.val()) {
            const codes = this._cleanAndConvertCodesToArray($portalLotSerialNumber.val());
            const res = await this.rpc("/helpdesk/check_scanned_code", {
                codes: codes,
                ticket_type: $ticketType.val(),
                partner_name: $partnerName.val(),
                partner_email: $partnerEmail.val(),
                tel_activation: tel_activation,
                by_pass_check: false,
            });

            if (!res || res.length === 0) return;

            for (const [keyName, keyMessage] of res) {
                if (["is_not_agency", "is_empty", "code_not_found", "code_already_registered"].includes(keyName)) {
                    return this.notification.add(_t(keyMessage), {
                        type: "warning",
                    });
                }
            }
        }

        if (!this.canSubmitTicket || is_attachment_empty) { return; }

        debugger;
    },

    /**
     * Handles the submit button click event on Activation Warranty Form.
     * @private
     * @param {Event} ev
     */
    async _onSubmitActivationButton(ev) {
        ev.preventDefault();

        const $ticketType = $("#helpdesk_warranty_select_ticket_type_id");
        const ticketTypeObj = await this._fetchTicketType($ticketType.val());

        const $partnerName = $("#helpdeskWarrantyInputPartnerName");
        const $partnerEmail = $("#helpdeskWarrantyInputPartnerEmail");
        const $portalLotSerialNumber = $("#helpdesk_warranty_input_portal_lot_serial_number");

        const phonePattern = /^[0-9]{10}$/; // Only digits, exactly 10 characters
        const $telNumberActivation = $("#helpdesk_warranty_input_tel_activation");
         if ($telNumberActivation.val() && !phonePattern.test($telNumberActivation.val())) {
            this.notification.add(
                ERROR_MESSAGES.INVALID_PHONE_PATTERN,
                { type: "warning" }
            );
            this.canSubmitTicket = false;
        }

        const validationErrors = await this._validateFormFields($partnerName, $partnerEmail, $portalLotSerialNumber);
        if (validationErrors.length > 0) {
            this.notification.add(
                ERROR_MESSAGES.EMPTY_REQUIRED_FIELDS,
                { type: "danger" }
            );
            this.canSubmitTicket = false;
        }

        let isEndUserType = ticketTypeObj && ticketTypeObj[0] && ticketTypeObj[0].code === "kich_hoat_bao_hanh_nguoi_dung_cuoi";
        if (isEndUserType) {
            const $licensePlatesActivation = $("#helpdesk_warranty_input_license_plates");
            const $mileageActivation = $("#helpdesk_warranty_input_mileage");

            const validationTicketTypeErrors = this._validateFormTicketTypeFields($telNumberActivation, $licensePlatesActivation, $mileageActivation);
            if (validationTicketTypeErrors.length > 0) {
                this.notification.add(
                    ERROR_MESSAGES.EMPTY_REQUIRED_FIELDS,
                    { type: "danger"}
                );
                this.canSubmitTicket = false;
            }
        }

        // Check scanned codes
        if ($portalLotSerialNumber.val()) {
            const codes = this._cleanAndConvertCodesToArray($portalLotSerialNumber.val());
            const res = await this.rpc("/helpdesk/check_scanned_code", {
                codes: codes,
                ticket_type: $ticketType.val(),
                partner_name: $partnerName.val(),
                partner_email: $partnerEmail.val(),
                tel_activation: null,
                by_pass_check: false,
            });

            if (!res || res.length === 0) return;

            for (const [keyName, keyMessage] of res) {
                if (["is_not_agency", "is_empty", "code_not_found", "code_already_registered"].includes(keyName)) {
                    return this.notification.add(_t(keyMessage), {
                        type: "warning",
                    });
                }
            }
        }

        if (!this.canSubmitTicket) { return; }
    },

    //--------------------------------------------------------------------------
    // Private Methods
    //--------------------------------------------------------------------------

    /**
     * Initialize services
     */
    _initializeServices() {
        this.orm = this.bindService("orm");
        this.rpc = this.bindService("rpc");
        this.dialogService = this.bindService("dialog");
        this.notification = this.bindService("notification");
    },

    /**
     * Populate form fields from cookies
     */
    _populateFormFromCookies() {
        if (document.cookie) {
            for (let val of document.cookie.split(';')) {
                if (val.trim().includes("+mvp_")) {
                    let tmp_string = val.split('+mvp_');
                    $("#helpdesk_warranty_input_license_plates").html(tmp_string[1].trim());
                    $("#helpdesk_warranty_input_mileage").html(tmp_string[2].trim());
                    $("#helpdesk_warranty_input_mv_warranty_phone").html(tmp_string[3].trim());
                    $("#helpdesk_warranty_input_mv_remaining_tread_depth").html(tmp_string[4].trim());
                    $("#helpdesk_warranty_input_mv_note_sub_branch").html(tmp_string[5].trim());
                    $("#helpdesk_warranty_input_portal_lot_serial_number").html(tmp_string[6].trim());
                }
            }
        }
    },

    /**
     * Clear cookies
     */
    _clearCookies() {
        document.cookie.replace(/(?<=^|;).+?(?=\=|;|$)/g, name => location.hostname.split('.').reverse().reduce(domain => (domain=domain.replace(/^\.?[^.]+/, ''),document.cookie=`${name}=;max-age=0;path=/;domain=${domain}`,domain), location.hostname));
    },

    /**
     * Validates the phone number.
     *
     * @param {string} phoneNumber - The phone number to validate.
     * @param {jQuery} $errorMessage - The error message element.
     * @returns {boolean} - True if the phone number is valid, false otherwise.
     */
    _validatePhoneNumber(phoneNumber, $errorMessage) {
        // Regular expression for mobile phone numbers
        let mobilePhoneRegex = /^(?:(?:\+|00)([1-9]\d{0,2}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})$/;
        // Regular expression for desk phone numbers starting with "028"
        let deskPhoneRegex = /^0(1[2-9]|2[03478])\d{8}$/;

        if (!phoneNumber) {
            $errorMessage.text(ERROR_MESSAGES.EMPTY_PHONE_NUMBER).addClass("invalid-feedback").show();
            $("#o_website_helpdesk_search_phone_number").addClass("border-danger is-invalid");
            return false;
        } else if (phoneNumber && !mobilePhoneRegex.test(phoneNumber) && !deskPhoneRegex.test(phoneNumber)) {
            $errorMessage.text(ERROR_MESSAGES.INVALID_PHONE_NUMBER).addClass("invalid-feedback").show();
            $("#o_website_helpdesk_search_phone_number").addClass("border-danger is-invalid");
            return false;
        }

        $errorMessage.hide();
        $("#o_website_helpdesk_search_phone_number").removeClass("border-danger is-invalid");
        return true;
    },

    /**
     * Fetches the partner's information.
     *
     * @param {string} phoneNumber - The phone number to use for fetching the partner's information.
     * @param {jQuery} $errorMessage - The error message element.
     */
    async _fetchPartnerInfo(phoneNumber, $errorMessage) {
        try {
            const data = await this.rpc("/helpdesk/check_partner_phone", { phone_number: phoneNumber });

            if (data["partner_not_found"]) {
                $errorMessage.text(ERROR_MESSAGES.PARTNER_NOT_FOUND).addClass("invalid-feedback").show();
                $("#o_website_helpdesk_search_phone_number").addClass("border-danger is-invalid");
            } else {
                $errorMessage.hide();
                $("#o_website_helpdesk_search_phone_number").removeClass("border-danger is-invalid");
                $("#o_website_helpdesk_search_phone_number, #helpdeskWarrantyInputPartnerName, #helpdeskWarrantyInputPartnerEmail").removeClass("border-danger");
                $("#helpdeskWarrantyInputPartnerName").val(data.partner_name || "");
                $("#helpdeskWarrantyInputPartnerEmail").val(data.partner_email || "");
            }
        } catch (e) {
            console.error("Failed to fetch partner info: ", e);
        }
    },

    /**
     * Validate form fields
     * @param {jQuery} $partnerName
     * @param {jQuery} $partnerEmail
     * @param {jQuery} $portalLotSerialNumber
     * @returns {Array} validationErrors
     */
    async _validateFormFields($partnerName, $partnerEmail, $portalLotSerialNumber) {
        const validationErrors = [];
        
        if (!$partnerName.val().trim()) {
            $partnerName.attr("required", true).addClass("border-danger");
            validationErrors.push("Partner name is required");
        }
        
        if (!$partnerEmail.val().trim()) {
            $partnerEmail.attr("required", true).addClass("border-danger");
            validationErrors.push("Partner email is required");
        }

        if (!$portalLotSerialNumber.val().trim()) {
            $portalLotSerialNumber.attr("required", true).addClass("border-danger");
            validationErrors.push("Portal lot serial number is required");
        } else { $portalLotSerialNumber.removeClass("border-danger"); }
        return validationErrors;
    },
    
    /**
     * Validate form fields
     * @param {jQuery} $telNumberActivation
     * @param {jQuery} $licensePlatesActivation
     * @param {jQuery} $mileageActivation
     * @returns {Array} validationErrors
     */
    _validateFormTicketTypeFields($telNumberActivation, $licensePlatesActivation, $mileageActivation) {
        const validationTicketTypeErrors = [];
        
        if (!$telNumberActivation.val().trim()) {
            validationTicketTypeErrors.push("Phone Activation is required");
        }
        
        if (!$licensePlatesActivation.val().trim()) {
            validationTicketTypeErrors.push("License plates is required");
        }
        
        if (!$mileageActivation.val().trim()) {
            validationTicketTypeErrors.push("Mileage (Km) is required");
        }
        
        return validationTicketTypeErrors;
    },

    /**
     * Fetch ticket type.
     */
    async _fetchTicketType(ticketTypeId) {
        try {
            return await this.orm.call("helpdesk.ticket.type", "search_read", [], {
                fields: ["id", "name", "code"],
                domain: [["user_for_warranty_activation", "=", true], ["id", "=", +ticketTypeId || false]],
            });
        } catch (e) {
            console.error("Failed to fetch ticket type: ", e);
        }
    },

    /**
     * Fetch claim ticket.
     */
    async _fetchClaimTicket(ticketTypeId) {
        try {
            return await this.orm.call("helpdesk.ticket.type", "search_read", [], {
                fields: ["id", "code"],
                domain: [["id", "=", +ticketTypeId || false]],
            });
        } catch (e) {
            console.error("Failed to fetch claim ticket: ", e);
        }
    },

    /**
     * Get telephone activation.
     */
    async _getTelActivation(partnerEmail, partnerName) {
        const domain = ['|', ['email', '=', partnerEmail], ['name', '=', partnerName]];
        const res = await this.orm.searchRead("res.partner", domain, ['name', 'email', 'phone', 'mobile'], { limit: 1 });
        return res[0].phone || res[0].mobile || null;
    },

    /**
     * Check scanned codes.
     */
    async _checkScannedCodes(codes, ticketTypeId, partnerName, partnerEmail, tel_activation) {
        return await this.rpc("/helpdesk/check_scanned_code", {
            codes: codes,
            ticket_type: ticketTypeId,
            partner_name: partnerName,
            partner_email: partnerEmail,
            tel_activation: tel_activation,
            by_pass_check: false,
        });
    },

    /**
     * Set cookie
     */
    _setCookie() {
        const now = new Date();
        now.setTime(now.getTime() + 9000); // 1000 * 9

        const fields = [
            "#helpdesk_warranty_input_license_plates",
            "#helpdesk_warranty_input_mileage",
            "#helpdesk_warranty_input_mv_warranty_phone",
            "#helpdesk_warranty_input_mv_remaining_tread_depth",
            "#helpdesk_warranty_input_mv_note_sub_branch",
            "#helpdesk_warranty_input_portal_lot_serial_number"
        ];

        const str_tmp = fields.map(selector => `+mvp_${$(selector).val()}`).join('');
        document.cookie = `${str_tmp};expires=${now.toUTCString()}`;
    },
    
    /**
     * Clean and convert codes to array
     * @param {string} codes
     * @returns {Array} codes
     */
    _cleanAndConvertCodesToArray(codes) {
        codes = codes.replace(/\s+/g, ""); // Remove all spaces
        codes = codes.replace(/,$/, ""); // Remove the trailing comma if it exists
        return codes.split(",");
    },

    /**
     * Redirect to claim warranty page
     * FIXME: This is a temporary solution to redirect to claim warranty page
     */
    async returnClaimWarranty() {
        try {
            const response = await fetch("/claim-bao-hanh", {
                method: "GET",
                headers: {
                    "Content-Type": "application/json",
                },
            });

            if (response.ok) {
                window.location.replace("/claim-bao-hanh");
            } else {
                console.error("Failed to redirect: ", response.statusText);
            }
        } catch (error) {
            console.error("Error during AJAX request: ", error);
        }
    },
});

export const helpdeskWarrantyForm = publicWidget.registry.HelpdeskWarrantyForm;