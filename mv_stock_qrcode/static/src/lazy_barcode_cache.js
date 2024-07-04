/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import LazyBarcodeCache from '@stock_barcode/lazy_barcode_cache';


patch(LazyBarcodeCache.prototype, {
    /**
     * @override by MOVEOPLUS
     */

    _constructor() {
        super._constructor(...arguments);
        this.barcodeFieldByModel['stock.move.line'] = 'qr_code';
    },

});
