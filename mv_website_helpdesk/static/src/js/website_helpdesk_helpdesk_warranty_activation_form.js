/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";


/**
 * Widget Portal Warranty Activation Form
 */
publicWidget.registry.helpdeskWarrantyActivationForm = publicWidget.Widget.extend({
    selector: '#helpdesk_warranty_activation_form',
    events: {
        'click #search-btn': '_onSearchButton',
        'click #submit-btn': '_onSubmitButton',
    },

    /**
     * @constructor
     */
    init: function () {
        this._super.apply(this, arguments);
        this.rpc = this.bindService("rpc");
        this.isPartner = false;
    },

    /**
     * @override
     */
    willStart() {
        return Promise.all([
            this._super(),
        ]);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    async _onSearchButton (ev) {
        const phoneNumber = $('#search-phone-number').val();
        if (!phoneNumber) {
            $('#phonenumber-error-message').removeClass('alert-warning').hide();
            $(ev.currentTarget).addClass('border-warning');
            $('#phonenumber-error-message').text(_t('Vui lòng nhập số điện thoại của bạn.')).addClass('alert-warning').show();
            return;
        }
        const data = await this.rpc('/mv_website_helpdesk/check_partner_phone_number',
            {
                phone_number: phoneNumber
            }
        );
        if (data.partner_not_found)  {
            $('#phonenumber-error-message').removeClass('alert-warning').hide();
            $(ev.currentTarget).addClass('border-warning');
            $('#phonenumber-error-message').text(_t('Không tìm thấy thông tin của bạn trên hệ thống, \nvui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin.')).addClass('alert-warning').show();
        } else if (data.number_parse_exception_failed)  {
            $('#phonenumber-error-message').removeClass('alert-warning').hide();
            $(ev.currentTarget).addClass('border-warning');
            $('#phonenumber-error-message').text(_t("Vui lòng nhập số điện thoại theo đúng định dạng quốc tế. Ví dụ: +32123456789.")).addClass('alert-warning').show();
        } else if (data.invalid_phone_number) {
            $('#phonenumber-error-message').removeClass('alert-warning').hide();
            $(ev.currentTarget).addClass('border-warning');
            $('#phonenumber-error-message').text(_t("Vui lòng nhập một số điện thoại hợp lệ.")).addClass('alert-warning').show();
        } else if (data.countries_support) {
            $('#phonenumber-error-message').removeClass('alert-warning').hide();
            $(ev.currentTarget).addClass('border-warning');
            $('#phonenumber-error-message').text(_t("Currently, only European countries are supported.")).addClass('alert-warning').show();
        } else {
            $(ev.currentTarget).removeClass('border-warning');
            $('#phonenumber-error-message').removeClass('alert-warning').hide();
        }

        const inputPartnerName = $("#helpdesk_warranty_input_partner_name");
        const inputPartnerEmail = $("#helpdesk_warranty_input_partner_email");
        if (data) {
            this.isPartner = true;
            inputPartnerName.attr('value', data.partner_name || '');
            inputPartnerEmail.attr('value', data.partner_email || '');
        } else {
            this.isPartner = true;
            inputPartnerName.attr('value', '');
            inputPartnerEmail.attr('value', '');
        }
    },

    async _onSubmitButton (ev) {
        const $partnerName = $('#helpdesk_warranty_input_partner_name');
        const $partnerEmail = $('#helpdesk_warranty_input_partner_email');
        const $portalLotSerialNumber = $('#helpdesk_warranty_input_portal_lot_serial_number');

        const is_partnerName_empty = !$partnerName.length || $partnerName.val().trim() === '';
        const is_partnerEmail_empty = !$partnerEmail.length || $partnerEmail.val().trim() === '';
        const is_portalLotSerialNumber_empty = !$portalLotSerialNumber.length || $portalLotSerialNumber.val().trim() === '';

        if (is_partnerName_empty) {
            $partnerName.attr('required', true);
        } else if (is_partnerEmail_empty) {
            $partnerEmail.attr('required', true);
        } else if (is_portalLotSerialNumber_empty) {
            $portalLotSerialNumber.attr('required', true);
        } else {
            $partnerName.attr('required', false);
            $partnerEmail.attr('required', false);
            $portalLotSerialNumber.attr('required', false);
        }
    },
});
