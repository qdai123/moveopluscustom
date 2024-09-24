/** @odoo-module **/

import { ListRenderer } from "@web/views/list/list_renderer";
import { patch } from "@web/core/utils/patch";


patch(ListRenderer.prototype, {
    /**
     * @override by MOVEOPLUS
     */

    freezeColumnWidths() {
        const tableList = this.tableRef.el;
        const childOfTableList = tableList.firstElementChild.firstElementChild;

        if (!$(childOfTableList.firstChild).hasClass("o_list_row_count")) {
            const col = $(childOfTableList).prepend(
                '<th class="o_list_row_number_header o_list_row_count" style="width: 4% !important;">'
            );
            col.find("th.o_list_row_count").html("#");
        }

        return super.freezeColumnWidths();
    },
});
