/** @odoo-module **/

import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

class HelpdeskWarrantyFormValidation extends Component {
    setup() {
        this.rpc = useService('rpc');
        this.orm = useService('orm');
    }

    /**
     * Validates the form before submission.
     *
     * @param {Event} event - The form submission event.
     */
    validateForm(event) {
        const fieldValue = this.el.querySelector('#helpdesk_warranty_input_portal_lot_serial_number').value;

        // Perform validation logic
        if (!fieldValue) {
            // Prevent form submission
            event.preventDefault();

            // Display error message
            this.displayAlert('Field is required.');
        }
        // Add more validation logic as needed
    }

    /**
     * Displays an alert message.
     *
     * @param {string} message - The message to display.
     */
    displayAlert(message) {
        this.env.services.notification.add(message);
    }
}

HelpdeskWarrantyFormValidation.template = 'mv_website_helpdesk.HelpdeskWarrantyFormValidation';
HelpdeskWarrantyFormValidation.props = {};

// Register the component
Component.registry.add('HelpdeskWarrantyFormValidation', HelpdeskWarrantyFormValidation);

export default HelpdeskWarrantyFormValidation;
