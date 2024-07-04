/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";
import { MainMenu } from "@stock_barcode/main_menu";


patch(MainMenu.prototype, {

    setup() {
        super.setup();
    }

});
