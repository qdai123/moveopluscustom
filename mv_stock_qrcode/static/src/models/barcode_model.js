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
        const codeScanning = barcode;
        let scanningQRCode = false;
        let scanningBarcode = false;

        let moveLinesObj = Object.values(this.cache.dbIdCache['stock.move.line']);
        if (moveLinesObj) {
            let listQRCodeToCompare = moveLinesObj.map(rec => rec.qr_code);
            if (listQRCodeToCompare.includes(codeScanning)) {
                scanningQRCode = true;
            } else {
                scanningBarcode = true;
            }
        } else {
            scanningBarcode = true;
        }

        // Validate: Picking DONE
        if (this.isDone && !this.commands[codeScanning]) {
            return this.notification(_t("Picking is already DONE!"), { type: "danger" });
        }

        if (scanningQRCode) {
            const moveLineObj = await this.orm.searchRead(
                "stock.move.line",
                [["picking_id", "in", this.recordIds], ["qr_code", "=", codeScanning]],
                ["id", "product_id", "lot_name", "inventory_period_name", "qr_code", "quantity"]
            );
            this.actionMutex.exec(() => this._processQRCode(codeScanning, moveLineObj));
        } else {
            this.actionMutex.exec(() => this._processBarcode(codeScanning));
        }
    },

    // --------------------------------------------------------------------------
    // Private
    // --------------------------------------------------------------------------

});
