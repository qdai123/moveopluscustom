/** @odoo-module **/

import {_t} from "@web/core/l10n/translation";
import {Component} from "@odoo/owl";
import {Dialog} from "@web/core/dialog/dialog";
import {useBus, useService, useChildRef} from "@web/core/utils/hooks";
import {isBarcodeScannerSupported} from "@web/webclient/barcode/barcode_scanner";
import * as BarcodeScanner from "@web/webclient/barcode/barcode_scanner";

// Define constants
const SPACE_REGEX = /\s+/g;
const TRAILING_COMMA_REGEX = /,$/;

export class ScannerDialog extends Component {
    setup() {
        this.modalRef = useChildRef();
        this.orm = useService("orm");
        this.rpc = useService("rpc");
        this.notificationService = useService("notification");
        this.dialogService = useService("dialog");
        this.isBarcodeScannerSupported = isBarcodeScannerSupported();
        this.barcodeService = useService("barcode");
        this.codes = ""; // Add a state to store the codes
        useBus(this.barcodeService.bus, "barcode_scanned", (ev) => this._onBarcodeScanned(ev.detail.barcode));
    }

    get facingMode() {
        return "environment";
    }

    /**
     * Opens the mobile scanner.
     * It uses the BarcodeScanner to scan a barcode.
     * If a barcode is scanned, it triggers the "barcode_scanned" event.
     * If no barcode is scanned, it shows a warning notification.
     */
    async openMobileScanner() {
        try {
            const barcode = await BarcodeScanner.scanBarcode(this.env);
            if (barcode) {
                this.barcodeService.bus.trigger("barcode_scanned", {barcode});
                if ("vibrate" in window.navigator) {
                    window.navigator.vibrate(100);
                }
            } else {
                this.env.services.notification.add(_t("Please, Scan again!"), {
                    type: "warning",
                });
            }
        } catch (e) {
            console.error("Failed to open mobile scanner: ", e);
        }
    }

    /**
     * Handles the barcode scanned event.
     * It cleans the scanned code and sends it to the server for validation.
     * If the server returns an error, it shows a warning notification.
     * If the server returns a valid code, it adds the code to the input field.
     * @param {string} code - The scanned barcode.
     */
    async _onBarcodeScanned(code) {
        if (!code) return;

        const listCode = this._cleanAndConvertCodesToArray(code);
        const $ticketType = $("#helpdesk_warranty_select_ticket_type_id");
        const $partnerEmail = $("#helpdeskWarrantyInputPartnerEmail");
        const $telNumberActivation = $("#helpdesk_warranty_input_tel_activation");
        try {
            const res = await this.rpc("/mv_website_helpdesk/check_scanned_code", {
                codes: listCode,
                ticket_type: $ticketType.val(),
                partner_email: $partnerEmail.val(),
                tel_activation: $telNumberActivation.val(),
                by_pass_check: true,
            });

            if (!res || res.length === 0) return;

            for (const [keyName, keyMessage] of res) {
                if (["is_empty", "code_not_found"].includes(keyName)) {
                    this.notificationService.add(_t(keyMessage), {
                        type: "warning",
                    });
                    return;
                } else {
                    const inputData = document.getElementById("codesInputByScanner");
                    // Use the state to store the codes instead of manipulating the DOM directly
                    if (!inputData.value.includes(res)) {
                        inputData.value += res + ",";
                    }
                    this.beep(50, 1000, 200);
                }
            }
        } catch (e) {
            console.error("Failed to scan barcode: ", e);
        }
    }

    beep(vol, freq, duration) {
        const audioContext = new AudioContext();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        oscillator.connect(gainNode);
        oscillator.frequency.value = freq;
        oscillator.type = "square";

        gainNode.connect(audioContext.destination);
        gainNode.gain.value = vol * 0.01;

        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + duration * 0.001);
    }

    _cleanAndConvertCodesToArray(codes) {
        codes = codes.replace(/\s+/g, ""); // Remove all spaces
        codes = codes.replace(/,$/, ""); // Remove the trailing comma if it exists
        return codes.split(",");
    }

    async _cancel() {
        return this.execButton(this.props.cancel);
    }

    async _confirm() {
        const getData = $("#codesInputByScanner").val();
        const listCode = this._cleanAndConvertCodesToArray(getData);
        return this.execButton(this.props.confirm(listCode));
    }

    setButtonsDisabled(disabled) {
        if (!this.modalRef.el) {
            return; // safety belt for stable versions
        }
        for (const button of [...this.modalRef.el.querySelectorAll(".modal-footer button")]) {
            button.disabled = disabled;
        }
    }

    async execButton(callback) {
        this.setButtonsDisabled(true);
        this.props.close();
    }
}

ScannerDialog.template = "mv_website_helpdesk.ScannerDialog";
ScannerDialog.components = {Dialog};
ScannerDialog.props = {
    close: Function,
    onBarcodeScanned: {type: Function},
    title: {
        validate: (m) => {
            return typeof m === "string" || (typeof m === "object" && typeof m.toString === "function");
        },
        optional: true,
    },
    body: String,
    confirm: {type: Function, optional: true},
    confirmLabel: {type: String, optional: true},
    confirmClass: {type: String, optional: true},
    cancel: {type: Function, optional: true},
    cancelLabel: {type: String, optional: true},
};
ScannerDialog.defaultProps = {
    confirmLabel: _t("Xác nhận"),
    cancelLabel: _t("Huỷ bỏ"),
    confirmClass: "btn-primary",
    title: _t("Quét Mã Vạch Hoặc QR-Code Sản Phẩm"),
};
