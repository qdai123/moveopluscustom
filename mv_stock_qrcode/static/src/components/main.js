/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import MainComponent from "@stock_barcode/components/main";


patch(MainComponent.prototype, {

    setup(...args) {
        super.setup(...args);
    }

});
