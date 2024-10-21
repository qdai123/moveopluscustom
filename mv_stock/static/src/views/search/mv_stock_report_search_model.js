/** @odoo-module **/

import { onWillStart } from "@odoo/owl";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { StockReportSearchModel } from "@stock/views/search/stock_report_search_model";

patch(StockReportSearchModel.prototype, {
    setup() {
        super.setup(...arguments);
        this.user = useService("user");
        onWillStart(async () => {
            this.isStockUser = await this.user.hasGroup('stock.group_stock_user');
            this.isStockManager = await this.user.hasGroup('stock.group_stock_manager');
        });
    },

    /**
        @ override
        * MO+ Customization
        * Load the warehouses based on the current user's group is Stock Users
    */

    async _loadWarehouses() {
        await super._loadWarehouses();

        const userId = this.user.userId || this.context.uid;
        const domain = [];

        if (this.isStockUser && !this.isStockManager) {
            this.warehouses = await this.orm.call(
                'stock.warehouse',
                'get_current_warehouses_by_user_access',
                [[]],
                { context: this.context }
            );
        }
    }
});