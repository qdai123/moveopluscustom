/** @odoo-module **/

import { useService } from "@web/core/utils/hooks";

import { markup } from "@odoo/owl";
import { _t } from "@web/core/l10n/translation";
import publicWidget from "@web/legacy/js/public/public_widget";

import { ScannerDialog } from "../components/scanner_dialog/scanner_dialog";
import { ConfirmationDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

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

        // Parameters:
        this.$inputSearchPhoneNumber = false;
        this.$inputPartnerName = false;
        this.$inputPartnerEmail = false;
    },

    async willStart() {
        this.$inputSearchPhoneNumber = this.el.querySelector(".o_website_helpdesk_search_phone_number");
        this.$inputPartnerName = this.el.querySelector("#helpdeskWarrantyInputPartnerName");
        this.$inputPartnerEmail = this.el.querySelector("#helpdeskWarrantyInputPartnereEmail");
        return Promise.all([this._super()]);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    openScannerDialog() {
        this.dialogService.add(ScannerDialog, {
            body: _t("Please, scanning your Lot/Serial Number here!"),
            onBarcodeScanned: async (scannedCode) => {
                const code = scannedCode || "";
                return code;
            },
            confirm: (codes) => {
                const inputPortalSerialNumber = document.getElementById(
                    "helpdesk_warranty_input_portal_lot_serial_number",
                );
                for (let i = 0; i < codes.length; ++i) {
                    if (!inputPortalSerialNumber.value.includes(codes[i])) {
                        inputPortalSerialNumber.value += codes[i] + ",";
                    }
                }
            },
            cancel: () => {},
        });
    },

    /**
     * @private
     * @param {Event} ev
     */

    async _onSearchButton(ev) {
        let phoneRegex = /^(?:(?:\+|00)([1-9]\d{0,2}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})$/;
        const phoneNumber = $(".o_website_helpdesk_search_phone_number").val();
        const $searchButton = $(ev.currentTarget);
        const $errorMessage = $("#phonenumber-error-message");

        if (!phoneNumber) {
            $errorMessage.text(_t("Vui lòng nhập số điện thoại của bạn.")).addClass("alert-warning").show();
            $searchButton.addClass("border-warning");
            return;
        } else if (phoneNumber && !phoneRegex.test(phoneNumber)) {
            $errorMessage.text(_t("Số điện thoại không hợp lệ.")).addClass("alert-warning").show();
            $searchButton.addClass("border-warning");
            return;
        }

        const data = await this.rpc("/mv_website_helpdesk/validate_partner_phonenumber", {
            phone_number: phoneNumber,
        });

        if (data.partner_not_found) {
            $errorMessage
                .text(
                    _t(
                        "Không tìm thấy thông tin theo số điện thoại của bạn.\n\n Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin.",
                    ),
                )
                .addClass("alert-warning")
                .show();
            $searchButton.addClass("border-warning");
        } else {
            $errorMessage.hide();
            $searchButton.removeClass("border-warning");
            $(
                ".o_website_helpdesk_search_phone_number, #helpdeskWarrantyInputPartnerName, #helpdeskWarrantyInputPartnerEmail",
            ).removeClass("border-danger");
            $("#helpdeskWarrantyInputPartnerName").val(data.partner_name || "");
            $("#helpdeskWarrantyInputPartnerEmail").val(data.partner_email || "");
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    async _onSubmitButton(ev) {
        ev.preventDefault();

        const $phoneNumber = $(".o_website_helpdesk_search_phone_number");
        const $partnerName = $("#helpdeskWarrantyInputPartnerName");
        const $partnerEmail = $("#helpdeskWarrantyInputPartnerEmail");
        const $portalLotSerialNumber = $("#helpdesk_warranty_input_portal_lot_serial_number");

        const is_partnerName_empty = !$partnerName.val().trim();
        const is_partnerEmail_empty = !$partnerEmail.val().trim();
        const is_portalLotSerialNumber_empty = !$portalLotSerialNumber.val().trim();

        if ($portalLotSerialNumber.val()) {
            const codes = $portalLotSerialNumber.val();
            const listCode = this._cleanAndConvertCodesToArray(codes);
            const res = await this.rpc("/mv_website_helpdesk/validate_scanned_code", { codes: listCode });

            if (!res || res.length === 0) return;

            for (const [keyName, keyMessage] of res) {
                if (["is_empty", "code_not_found", "code_already_registered"].includes(keyName)) {
                    return this.notification.add(_t(keyMessage), {
                        type: "warning",
                    });
                }
            }
        }

        if (is_partnerName_empty && is_partnerEmail_empty && is_portalLotSerialNumber_empty) {
            $partnerName.attr("required", true);
            $partnerEmail.attr("required", true);
            $portalLotSerialNumber.attr("required", true);
            $phoneNumber.addClass("border-danger");
        } else {
            $partnerName.attr("required", is_partnerName_empty);
            $partnerEmail.attr("required", is_partnerEmail_empty);
            $portalLotSerialNumber.attr("required", is_portalLotSerialNumber_empty);

            if (is_partnerName_empty) {
                $partnerName.addClass("border-danger");``
            } else if (is_partnerEmail_empty) {
                $partnerEmail.addClass("border-danger");
            } else if (is_portalLotSerialNumber_empty) {
                $portalLotSerialNumber.addClass("border-danger");
            }
        }

        if (is_partnerName_empty || is_partnerEmail_empty || is_portalLotSerialNumber_empty) {
            return this.notification.add(_t("Vui lòng nhập vào đủ thông tin yêu cầu!"), {
                type: "danger",
            });
        }
    },

    _cleanAndConvertCodesToArray(codes) {
        codes = codes.replace(/\s+/g, ""); // Remove all spaces
        codes = codes.replace(/,$/, ""); // Remove the trailing comma if it exists
        return codes.split(",");
    },
});
