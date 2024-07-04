/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import LineComponent from "@stock_barcode/components/line";


patch(LineComponent.prototype, {
    /**
     * @override by MOVEOPLUS
     */

    get qrCode() {
        return (this.line.qr_code || '');
    },

    get inventoryPeriod() {
        return (this.line.inventory_period_id && this.line.inventory_period_id.week_number_str) || this.line.inventory_period_name || '';
    },

});
