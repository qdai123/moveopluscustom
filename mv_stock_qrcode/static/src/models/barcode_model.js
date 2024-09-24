/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import BarcodeModel from "@stock_barcode/models/barcode_model";


patch(BarcodeModel.prototype, {
    /**
     * @override by MOVEOPLUS
     */

    constructor() {
        super.setup(...arguments);
    },

    setData() {
        super.setData(...arguments);
    },

    // ACTIONS

    async processBarcode(barcode) {
        let scanningQRCode = false;
        let scanningBarcode = false;
        const codeScanning = barcode;
        const stockOperationType = this.config.operation_type || '';

        if (stockOperationType && ["incoming", "outgoing"].includes(stockOperationType)) {
            let modelMoveLineEnv = Object.values(this.cache.dbIdCache['stock.move.line']);
            if (!modelMoveLineEnv) {
                scanningBarcode = true;
            } else {
                if (modelMoveLineEnv.map(rec => rec.qr_code).includes(codeScanning)) {
                    scanningQRCode = true;
                } else {
                    scanningBarcode = true;
                }
            }

            // Validate: Picking DONE
            if (this.isDone && !this.commands[codeScanning]) {
                return this.notification(
                    _t("Picking is already DONE!"),
                    { type: "danger" }
                );
            }

            const moveLineObj = await this.orm.searchRead(
                "stock.move.line",
                [["picking_id", "in", this.recordIds], ["qr_code", "=", codeScanning]],
                ["id", "product_id", "lot_name", "inventory_period_name", "qr_code", "quantity"]
            );
            if (scanningBarcode) {
                if (stockOperationType == "incoming") {
                    let productBarcodeExistInPageLines = this._checkProductBarcodeExistInPageLines(codeScanning);
                    let qrcodeExistInPageLines = this._checkQRCodeExistInPageLines(codeScanning);
                    let lotNameExistInPageLines = this._checkLotNameExistInPageLines(codeScanning);
                    if (!qrcodeExistInPageLines && (lotNameExistInPageLines || productBarcodeExistInPageLines)) {
                        this.actionMutex.exec(() => this._processBarcode(codeScanning));
                    } else {
                        this.actionMutex.exec(() => this._processQRCode(codeScanning, "incoming", moveLineObj));
                    }
                } else if (stockOperationType == "outgoing") {
                    this.actionMutex.exec(() => this._processQRCode(codeScanning, "outgoing", moveLineObj));
                }
            } else if (scanningQRCode) {
                this.actionMutex.exec(() => this._processQRCode(codeScanning, stockOperationType, moveLineObj));
            } else {
                return this.notification(
                    _t("The scanned code does not exist in the receipt list!"),
                    { type: "danger" }
                );
            }
        }
    },

    // --------------------------------------------------------------------------
    // Private
    // --------------------------------------------------------------------------

    _checkProductBarcodeExistInPageLines(code) {
        return this.pageLines.some(line => line.product_barcode === code);
    },

    _checkQRCodeExistInPageLines(code) {
        return this.pageLines.some(line => line.qr_code === code);
    },

    _checkLotNameExistInPageLines(code) {
        return this.pageLines.some(line => line.lot_name === code);
    }

});
