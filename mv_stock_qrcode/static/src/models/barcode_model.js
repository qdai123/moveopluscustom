/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import BarcodeModel from "@stock_barcode/models/barcode_model";


patch(BarcodeModel.prototype, {
    /**
     * @override by MOVEOPLUS
     */

    setData(data) {
        super.setData(...arguments);
        super.setData(data);
    },

    // GETTER

    get canCreateNewMoveLine() {
        return true;
    },

    get useExistingMoveLine() {
        return true;
    },

    // ACTIONS

    async processBarcode(barcode) {
        console.debug("MOVEOPLUS Debugging on Model: " + this.resModel);
        // console.debug("Print Cache: " + JSON.stringify(this.cache));
        this.actionMutex.exec(() => this._processBarcode(barcode));
    },

    createNewLine(params) {
        // return this._createNewLine(params);
        console.debug("Params Creation: " + params);
        return;
    },

    // --------------------------------------------------------------------------
    // Private
    // --------------------------------------------------------------------------

    _shouldSearchForAnotherMoveLine(code, filters) {
        return !code.match && filters['stock.move.line'] && !this.canCreateNewMoveLine && this.useExistingMoveLine;
    },

});
