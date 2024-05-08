/** @odoo-module **/

import { markup } from "@odoo/owl";

import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import publicWidget from "@web/legacy/js/public/public_widget";


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
        this.notification = this.bindService("notification");
        this.$inputSearchPhoneNumber = false;
        this.$inputPartnerName = false;
        this.$inputPartnerEmail = false;
    },

    /**
     * @override
     */
    start: function () {
        this.$inputSearchPhoneNumber = this.el.querySelector('.o_website_helpdesk_search_phone_number');
        this.$inputPartnerName = this.el.querySelector('#helpdesk_warranty_input_partner_name');
        this.$inputPartnerEmail = this.el.querySelector('#helpdesk_warranty_input_partner_email');

        return this._super.apply(this, arguments);
    },

    willStart() {
        return Promise.all([this._super()]);
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     * @param {Event} ev
     */
    async _onSearchButton (ev) {
        const phoneNumber = $('.o_website_helpdesk_search_phone_number').val();
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
            $('#phonenumber-error-message').text(_t('Không tìm thấy thông tin theo số điện thoại của bạn trên hệ thống. Vui lòng liên hệ bộ phận hỗ trợ của Moveo PLus để đăng ký thông tin.')).addClass('alert-warning').show();
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
            $('.o_website_helpdesk_search_phone_number').removeClass('border-danger');
            $('#helpdesk_warranty_input_partner_name').removeClass('border-danger');
            $('#helpdesk_warranty_input_partner_email').removeClass('border-danger');
            $('#phonenumber-error-message').removeClass('alert-warning').hide();
        }

        const inputPartnerName = $("#helpdesk_warranty_input_partner_name");
        const inputPartnerEmail = $("#helpdesk_warranty_input_partner_email");
        if (data) {
            inputPartnerName.attr('value', data.partner_name || '');
            inputPartnerEmail.attr('value', data.partner_email || '');
        } else {
            inputPartnerName.attr('value', '');
            inputPartnerEmail.attr('value', '');
        }
    },

    /**
     * @private
     * @param {Event} ev
     */
    async _onSubmitButton (ev) {
        ev.preventDefault();
        const $phoneNumber = $('.o_website_helpdesk_search_phone_number');
        const $partnerName = $('#helpdesk_warranty_input_partner_name');
        const $partnerEmail = $('#helpdesk_warranty_input_partner_email');

        const is_partnerName_empty = !$partnerName.length || $partnerName.val().trim() === '';
        const is_partnerEmail_empty = !$partnerEmail.length || $partnerEmail.val().trim() === '';
        let error = is_partnerName_empty || is_partnerEmail_empty;

        if (is_partnerName_empty && is_partnerEmail_empty) {
            $partnerName.attr('required', true);
            $partnerEmail.attr('required', true);
        } else {
            if (is_partnerName_empty) {
                $partnerName.attr('required', true);
            } else if (is_partnerEmail_empty) {
                $partnerEmail.attr('required', true);
            }
        }

        if (error) {
            if (is_partnerName_empty && is_partnerEmail_empty) {
                $phoneNumber.addClass('border-danger');
            } else if (is_partnerEmail_empty) {
                $partnerEmail.addClass('border-danger');
            } else if (is_partnerName_empty) {
                $partnerName.addClass('border-danger');
            }
            this.notification.add(_t("Vui lòng nhập vào thông tin của bạn!"), {
                type: "danger",
            });
            return;
        }
    },

    /**
     * @private
     */
    _onSubmitCheckContent: function () {
        const phoneNumber = this.$inputSearchPhoneNumber.value;
        const partnerName = this.$inputPartnerName.value;
        const partnerEmail = this.$inputPartnerEmail.value;

        if (!phoneNumber && !partnerName && !partnerEmail) {
            return {
                code: 'empty_all',
                message: _t('Một số trường là bắt buộc. Hãy đảm bảo điền vào những thông tin này.'),
            };
        } else if (!partnerName) {
            return {
                code: 'empty_partner_name',
                message: _t('Họ Tên không được để trống!'),
            };
        } else if (!partnerEmail) {
            return {
                code: 'empty_partner_email',
                message: _t('Email không được để trống!'),
            };
        }
    },
});
