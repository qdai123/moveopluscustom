/** @odoo-module **/

import {App, whenReady, Component, useState} from "@odoo/owl";
import { makeEnv, startServices } from "@web/env";
import { templates } from "@web/core/assets";
import { _t } from "@web/core/l10n/translation";
import { MainComponentsContainer } from "@web/core/main_components_container";
import { useService, useBus } from "@web/core/utils/hooks";
import { url } from "@web/core/utils/urls";
import {LotSerialNumberScanner} from "@mv_website_helpdesk/components/helpdesk_ticket_barcode/helpdesk_ticket_barcode";

class validateHelpdeskTicketLotSerialNumberApp extends Component{
    static props = [];
    static components = {
        LotSerialNumberScanner,
        MainComponentsContainer,
    };

    setup() {
        this.rpc = useService("rpc");
        this.barcode = useService("barcode");
        this.notification = useService("notification");
        this.lockScanner = false;
        console.log("12i31oi32y1oi231oi2u3y1oi2");
    }

    async validateLotSerialNumber(lotSerialNumber){
        const ticket = await this.rpc('helpdesk_ticket_lot_serial_number_scanned',
            {
                'lot_serial_number': lotSerialNumber
            })
        this.displayNotification(ticket);
    }

    displayNotification(text){
        this.notification.add(text, { type: "danger" });
    }

    async onBarcodeScanned(barcode){
        if (this.lockScanner) {
            return;
        }
        this.lockScanner = true;
        const result = await this.rpc('helpdesk_ticket_lot_serial_number_scanned',
            {
                'lot_serial_number': barcode
            })
        this.displayNotification(ticket);
        this.lockScanner = false;
    }
}

HelpdeskTicketScannerApp.template = "mv_website_helpdesk.public_helpdesk_ticket_scanner_app";

export async function validateLotSerialNumber(document, data_get) {
    await whenReady();
    const env = makeEnv();
    await startServices(env);
    const app = new App(HelpdeskTicketScannerApp, {
        templates,
        env: env,
        props:
            {
                data: data_get.data;
            },
        dev: env.debug,
        translateFn: _t,
        translatableAttributes: ["data-tooltip"],
    });
    return app.mount(document.body);
}
export default { HelpdeskTicketScannerApp, validateLotSerialNumber };
