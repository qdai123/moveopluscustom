/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import publicWidget from "@web/legacy/js/public/public_widget";
import {ScannerDialog} from "../components/scanner_dialog/scanner_dialog";

const ERROR_MESSAGES = {
    EMPTY_PHONE_NUMBER: "Vui lòng nhập số điện thoại của bạn.",
    INVALID_PHONE_NUMBER: "Số điện thoại không hợp lệ.",
    PARTNER_NOT_FOUND: "Không tìm thấy thông tin theo số điện thoại của bạn hoặc bạn không phải là Đại lý của Moveo Plus.\n\n Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin."
};

/**
 * Portal Warranty Activation Form View
 */
publicWidget.registry.helpdeskWarrantyActivationForm = publicWidget.Widget.extend({
    selector: "#helpdesk_warranty_activation_form",
    events: {
        "click #search-btn": "_onSearchButton",
        "click #submit-btn": "_onSubmitButton",
        "click #scanning-btn": "openScannerDialog",
    },
    
    /**
     * @constructor
     */
    init() {
        this._super(...arguments);
        this.orm = this.bindService("orm");
        this.rpc = this.bindService("rpc");
        this.dialogService = this.bindService("dialog");
        this.notification = this.bindService("notification");
    },
    
    async willStart() {
        return Promise.all([this._super()]);
    },
    
    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------
    
    /**
     * Opens the scanner dialog.
     * It creates a new ScannerDialog instance and adds it to the dialog service.
     * The dialog prompts the user to scan their Lot/Serial Number.
     * Once a barcode is scanned, it is added to the input field for Lot/Serial Number.
     */
    openScannerDialog() {
        try {
            this.dialogService.add(ScannerDialog, {
                body: _t("Please, scanning your Lot/Serial Number here!"),
                onBarcodeScanned: async (scannedCode) => {
                    // Ensure the scanned code is valid before returning it
                    return scannedCode ? scannedCode.trim() : "";
                },
                confirm: (codes) => {
                    const inputPortalSerialNumber = document.getElementById(
                        "helpdesk_warranty_input_portal_lot_serial_number",
                    );
                    for (let i = 0; i < codes.length; ++i) {
                        // Only add the code if it's not already in the input field
                        if (!inputPortalSerialNumber.value.includes(codes[i])) {
                            inputPortalSerialNumber.value += codes[i] + ",";
                        }
                    }
                },
                cancel: () => {
                    // Handle the cancel event if necessary
                },
            });
        } catch (e) {
            console.error("Failed to open scanner dialog: ", e);
        }
    },
    
    /**
     * Handles the search button click event. It validates the phone number and fetches the partner's information.
     *
     * @param {Event} ev - The click event.
     */
    async _onSearchButton(ev) {
        const $phoneNumber = $("#o_website_helpdesk_search_phone_number");
        const $searchButton = $(ev.currentTarget);
        const $errorMessage = $("#phonenumber-error-message");
        
        // Validate the phone number
        const isValidPhoneNumber = this._validatePhoneNumber($phoneNumber.val(), $searchButton, $errorMessage);
        if (!isValidPhoneNumber) {
            return;
        } else {
            $errorMessage.hide();
            $phoneNumber.removeClass("border-danger is-invalid");
        }
        
        // Fetch the partner's information
        await this._fetchPartnerInfo($phoneNumber.val(), $searchButton, $errorMessage);
    },
    
    /**
     * Validates the phone number.
     *
     * @param {string} phoneNumber - The phone number to validate.
     * @param {jQuery} $searchButton - The search button element.
     * @param {jQuery} $errorMessage - The error message element.
     * @returns {boolean} - True if the phone number is valid, false otherwise.
     */
    _validatePhoneNumber(phoneNumber, $searchButton, $errorMessage) {
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
        
        return true;
    },
    
    /**
     * Fetches the partner's information.
     *
     * @param {string} phoneNumber - The phone number to use for fetching the partner's information.
     * @param {jQuery} $searchButton - The search button element.
     * @param {jQuery} $errorMessage - The error message element.
     */
    async _fetchPartnerInfo(phoneNumber, $searchButton, $errorMessage) {
        try {
            const data = await this.rpc("/mv_website_helpdesk/check_partner_phone", {
                phone_number: phoneNumber,
            });
            
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
     * @private
     * @param {Event} ev
     */
    async _onSubmitButton(ev) {
        ev.preventDefault();
        
        // Fetch all the forms we want to apply custom Bootstrap validation styles to
        // const forms = document.querySelectorAll('.needs-validation');
        // console.log(forms);
        
        // Get form fields
        const $partnerName = $("#helpdeskWarrantyInputPartnerName");
        const $partnerEmail = $("#helpdeskWarrantyInputPartnerEmail");
        const $portalLotSerialNumber = $("#helpdesk_warranty_input_portal_lot_serial_number");
        
        // Validate form fields
        const validationErrors = this._validateFormFields($partnerName, $partnerEmail, $portalLotSerialNumber);
        if (validationErrors.length > 0) {
            this.notification.add(_t("Vui lòng nhập vào đủ thông tin yêu cầu!"), {
                type: "danger",
            });
            return;
        } else {
            $partnerName.removeClass("border-danger");
            $partnerEmail.removeClass("border-danger");
            $portalLotSerialNumber.removeClass("border-danger");
        }
        
        const $telNumberActivation = $("#helpdesk_warranty_input_tel_activation");
        const $licensePlatesActivation = $("#helpdesk_warranty_input_license_plates");
        const $mileageActivation = $("#helpdesk_warranty_input_mileage");
        
        const $ticketType = $("#helpdesk_warranty_select_ticket_type_id");
        let ticketTypeObj;
        try {
            ticketTypeObj = await this.orm.call("helpdesk.ticket.type", "search_read", [], {
                fields: ["id", "name", "code"],
                domain: [["user_for_warranty_activation", "=", true], ["id", "=", +$ticketType.val() || false]],
            });
        } catch (e) {
            console.error("Failed to fetch ticket type: ", e);
        }
        
        if (ticketTypeObj && ticketTypeObj[0] && ticketTypeObj[0].code === "kich_hoat_bao_hanh_nguoi_dung_cuoi") {
            // Validate form fields for Ticket Type
            const validationTicketTypeErrors = this._validateFormTicketTypeFields($telNumberActivation, $licensePlatesActivation, $mileageActivation);
            if (validationTicketTypeErrors.length > 0) {
                this.notification.add(_t("Vui lòng nhập vào đủ thông tin yêu cầu!"), {
                    type: "danger",
                });
                return;
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
            const res = await this.rpc("/mv_website_helpdesk/check_scanned_code", {
                codes: codes,
                ticket_type: $ticketType.val(),
                partner_name: $partnerName.val(),
                partner_email: $partnerEmail.val(),
                tel_activation: tel_activation,
                by_pass_check: false,
            });
            
            // TODO: Handle error response
            // const error = new RPCError();
            // console.debug("Error: ", error);
            
            if (!res || res.length === 0) return;
            
            for (const [keyName, keyMessage] of res) {
                if (["is_not_agency", "is_empty", "code_not_found", "code_already_registered"].includes(keyName)) {
                    return this.notification.add(_t(keyMessage), {
                        type: "warning",
                    });
                }
            }
        }
    },
    
    /**
     * Validate form fields
     * @param {jQuery} $partnerName
     * @param {jQuery} $partnerEmail
     * @param {jQuery} $portalLotSerialNumber
     * @returns {Array} validationErrors
     */
    _validateFormFields($partnerName, $partnerEmail, $portalLotSerialNumber) {
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
        }
        
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
     * Clean and convert codes to array
     * @param {string} codes
     * @returns {Array} codes
     */
    _cleanAndConvertCodesToArray(codes) {
        codes = codes.replace(/\s+/g, ""); // Remove all spaces
        codes = codes.replace(/,$/, ""); // Remove the trailing comma if it exists
        return codes.split(",");
    },
});
