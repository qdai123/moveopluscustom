/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import LazyBarcodeCache from '@stock_barcode/lazy_barcode_cache';


patch(LazyBarcodeCache.prototype, {
    /**
     * @override by MOVEOPLUS
     */

    constructor(cacheData) {
        this.setup(...arguments);
        this.setCache(cacheData);
    },

});
