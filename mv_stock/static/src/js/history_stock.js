/** @odoo-module */
import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';
import { useService } from "@web/core/utils/hooks";
import { session } from "@web/session";
export class MVHistoryStockController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
    }
    async PrintExImReport() {
        const stockObjects = await this.orm.call("mv.history.stock", "search_read", [], {
            fields: ["id"],
            domain: [["create_uid", "=", session.uid]],
        });
        if (stockObjects){
            await this.actionService.doAction({
                type: 'ir.actions.report',
                report_type: 'py3o',
                report_name: `py3o_mv_history_stock_info/${stockObjects[0].id}`,
                py3o_filetype: 'ods',
            });
        }
        else {
            return false
        }
    }
}

registry.category("views").add("history_stock_report_button", {
   ...listView,
   Controller: MVHistoryStockController,
   buttonTemplate: "mv_stock.ListView.Buttons",
});
