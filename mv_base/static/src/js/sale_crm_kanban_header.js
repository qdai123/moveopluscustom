/** @odoo-module */

import { KanbanHeader } from "@web/views/kanban/kanban_header";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";

patch(KanbanHeader.prototype, {
    setup() {
        super.setup();
        this.user = useService("user");
    },

    /**
     * @override
     */
    get permissions() {
        const permissions = super.permissions;
        Object.defineProperty(permissions, "canEditAutomations", {
            get: () => this.user.isAdmin || this.user.hasGroup("sales_team.group_sale_salesman"),
            configurable: true,
        });
        return permissions;
    }

})
