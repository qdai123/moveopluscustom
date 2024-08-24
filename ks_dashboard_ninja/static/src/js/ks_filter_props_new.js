/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import {KsDashboardNinja} from "@ks_dashboard_ninja/js/ks_dashboard_ninja_new";
import { _t } from "@web/core/l10n/translation";
import { renderToElement,renderToString,renderToFragment } from "@web/core/utils/render";
import { isBrowserChrome, isMobileOS } from "@web/core/browser/feature_detection";
import { Ksdashboardtile } from '@ks_dashboard_ninja/components/ks_dashboard_tile_view/ks_dashboard_tile';
import { getDomainDisplayedOperators } from "@web/core/domain_selector/domain_selector_operator_editor";
import { getOperatorLabel } from "@web/core/tree_editor/tree_editor_operator_editor";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
const { DateTime } = luxon;
import {formatDate,formatDateTime} from "@web/core/l10n/dates";
import {parseDateTime,parseDate,} from "@web/core/l10n/dates";
import { serializeDateTime, serializeDate } from "@web/core/l10n/dates";

const ks_field_type = {
    binary: "binary",
    boolean: "boolean",
    char: "char",
    date: "date",
    datetime: "datetime",
    float: "number",
    html: "char",
    id: "id",
    integer: "number",
    many2many: "char",
    many2one:"char",
    monetary: "number",
    one2many: "char",
    selection: "selection",
    text: "char"
}



patch(KsDashboardNinja.prototype,{
    ks_fetch_items_data(){
        var self = this;
        return super.ks_fetch_items_data().then(function(){
            if (self.ks_dashboard_data.ks_dashboard_domain_data) self.ks_init_domain_data_index();
        });
    },

    ks_init_domain_data_index(){
        var self = this;
        // TODO: Make domain data index from backend : loop wasted
        var temp_data = {};
        var to_insert = Object.values(this.ks_dashboard_data.ks_dashboard_pre_domain_filter).filter((x)=>{
            return x.type==='filter' && x.active && self.ks_dashboard_data.ks_dashboard_domain_data[x.model].ks_domain_index_data.length === 0
        });
        (to_insert).forEach((x)=>{
            if(x['categ'] in temp_data) {
               temp_data[x['categ']]['domain']= temp_data[x['categ']]['domain'].concat(x['domain']);
               temp_data[x['categ']]['label']= temp_data[x['categ']]['label'].concat(x['name']);
            } else {
                temp_data[x['categ']] = {'domain': x['domain'], 'label': [x['name']], 'categ': x['categ'], 'model': x['model']};
            }
        })
        Object.values(temp_data).forEach((x)=>{
            self.ks_dashboard_data.ks_dashboard_domain_data[x.model].ks_domain_index_data.push(x);
        })
    },
        onKsDnDynamicFilterSelect(ev){
        var self = this;
        if($(ev.currentTarget).hasClass('dn_dynamic_filter_selected')){
            self._ksRemoveDynamicFilter(ev.currentTarget.dataset['filterId']);
            $(ev.currentTarget).removeClass('dn_dynamic_filter_selected');
        } else {
            self._ksAppendDynamicFilter(ev.currentTarget.dataset['filterId']);
            $(ev.currentTarget).addClass('dn_dynamic_filter_selected');
        }
        var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
        if(storedData !== null ){
            this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
        }
        if(Object.keys(self.ks_dashboard_data.ks_dashboard_domain_data).length !==0){
            this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, self.ks_dashboard_data.ks_dashboard_domain_data, 1);
        }
    },

    _ksAppendDynamicFilter(filterId){
        // Update predomain data -> Add into Domain Index -> Add or remove class
        this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].active = true;

        var action = 'add_dynamic_filter';
        var categ = this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].categ;
        var params = {
            'model': this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].model,
            'model_name': this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].model_name,
        }
        this._ksUpdateAddDomainIndexData(action, categ, params);
    },

    _ksRemoveDynamicFilter(filterId){
         // Update predomain data -> Remove from Domain Index -> Add or remove class
        this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].active = false;

        var action = 'remove_dynamic_filter';
        var categ = this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].categ;
        var params = {
            'model': this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].model,
            'model_name': this.ks_dashboard_data.ks_dashboard_pre_domain_filter[filterId].model_name,
        }
        this._ksUpdateRemoveDomainIndexData(action, categ, params);
    },

    _ksUpdateAddDomainIndexData(action, categ, params){
        // Update Domain Index: Add or Remove model related data, Update its domain, item ids
        // Fetch records for the effected items
        // Re-render Search box of this name if the value is add
        var self = this;
        var model = params['model'] || false;
        var model_name = params['model_name'] || '';
        $(".ks_dn_filter_applied_container").removeClass('ks_hide');

        var filters_to_update = Object.values(this.ks_dashboard_data.ks_dashboard_pre_domain_filter).filter((x)=>{return x.active === true && x.categ === categ});
        var domain_data = self.ks_dashboard_data.ks_dashboard_domain_data[model];
        if (domain_data) {
            var domain_index = (domain_data.ks_domain_index_data).find((x)=>{return x.categ === categ});
            if (domain_index) {
                domain_index['domain'] = [];
                domain_index['label'] = [];
                (filters_to_update).forEach((x)=>{
                    if (domain_index['domain'].length>0) domain_index['domain'].unshift('|');
                    domain_index['domain'] = domain_index['domain'].concat(x['domain']);
                    domain_index['label'] = domain_index['label'].concat(x['name']);
                })
            } else {
                domain_index = {
                    categ: categ,
                    domain: [],
                    label: [],
                    model: model,
                };
                filters_to_update.forEach((x)=>{
                    if (domain_index['domain'].length>0) domain_index['domain'].unshift('|');
                    domain_index['domain'] = domain_index['domain'].concat(x['domain']);
                    domain_index['label'] = domain_index['label'].concat(x['name']);
                });
                domain_data.ks_domain_index_data.push(domain_index);
            }

        } else {
            var domain_index = {
                    categ: categ,
                    domain: [],
                    label: [],
                    model: model,
            };
            filters_to_update.forEach((x)=>{
                if (domain_index['domain'].length>0) domain_index['domain'].unshift('|');
                domain_index['domain'] = domain_index['domain'].concat(x['domain']);
                domain_index['label'] = domain_index['label'].concat(x['name']);
            });
            domain_data = {
                'domain': [],
                'model_name': model_name,
                'item_ids': self.ks_dashboard_data.ks_model_item_relation[model],
                'ks_domain_index_data': [domain_index],
            };
            self.ks_dashboard_data.ks_dashboard_domain_data[model] = domain_data;
        }

        domain_data['domain'] = self._ksMakeDomainFromDomainIndex(domain_data.ks_domain_index_data);
        self.state.pre_defined_filter = {...domain_data}
        self.state.ksDateFilterSelection = 'none'
        self.state.custom_filter = {}
    },

    _ksUpdateRemoveDomainIndexData(action, categ, params){
        var self = this;
        var model = params['model'] || false;
        var model_name = params['model_name'] || '';
        var filters_to_update = Object.values(this.ks_dashboard_data.ks_dashboard_pre_domain_filter).filter((x)=>{return x.active === true && x.categ === categ});
        var domain_data = self.ks_dashboard_data.ks_dashboard_domain_data[model];
        var domain_index = (domain_data.ks_domain_index_data).find((x)=>{return x.categ === categ});

        if (filters_to_update.length<1) {
            if (domain_data.ks_domain_index_data.length>1){
                domain_data.ks_domain_index_data.splice(domain_data.ks_domain_index_data.indexOf(domain_index),1);
//                $('.o_searchview_facet[data-ks-categ="'+ categ + '"]').remove();
            }else {
                $('.ks_dn_filter_section_container[data-ks-model-selector="'+ model + '"]').remove();
                delete self.ks_dashboard_data.ks_dashboard_domain_data[model];
                if(!Object.keys(self.ks_dashboard_data.ks_dashboard_domain_data).length){
                    $(".ks_dn_filter_applied_container").addClass('ks_hide');
                }
            }
        } else{
            domain_index['domain'] = [];
            domain_index['label'] = [];
            (filters_to_update).forEach((x)=>{
                if (domain_index['domain'].length>0) domain_index['domain'].unshift('|');
                domain_index['domain'] = domain_index['domain'].concat(x['domain']);
                domain_index['label'] = domain_index['label'].concat(x['name']);
            })
        }

        domain_data['domain'] = self._ksMakeDomainFromDomainIndex(domain_data.ks_domain_index_data);
        domain_data['ks_remove'] = true
         self.state.pre_defined_filter = {...domain_data}
         if(domain_data['domain'].length != 0){
                var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
                if(storedData !== null ){
                    this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
                }
                if(Object.keys(self.ks_dashboard_data.ks_dashboard_domain_data).length !==0){
                    this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, self.ks_dashboard_data.ks_dashboard_domain_data, 1);
                }
            }else{
                var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
                if(storedData){
                   this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
                }
            }
         self.state.ksDateFilterSelection = 'none'
         self.state.custom_filter = {}
    },

    _ksMakeDomainFromDomainIndex(ks_domain_index_data){
        var domain = [];
        (ks_domain_index_data).forEach((x)=>{
            if (domain.length>0) domain.unshift('&');
            domain = domain.concat((x['domain']));
        })
        return domain;
    },
    ksOnRemoveFilterFromSearchPanel(ev){
        var self = this;
        ev.stopPropagation();
        var $search_section = $(ev.currentTarget).parent();
        var model = $search_section.attr('ksmodel');
        if ($search_section.attr('kscateg') != '0'){
            var categ = $search_section.attr('kscateg');
            var action = 'remove_dynamic_filter';
            var $selected_pre_define_filter = $(".dn_dynamic_filter_selected.dn_filter_click_event_selector[data-ks-categ='"+ categ +"']");
            $selected_pre_define_filter.removeClass("dn_dynamic_filter_selected");
            ($selected_pre_define_filter).toArray().forEach((x)=>{
                var filter_id = $(x).data('filterId');
                self.ks_dashboard_data.ks_dashboard_pre_domain_filter[filter_id].active = false;
            })
            var params = {
                'model': model,
                'model_name': $search_section.attr('modelName'),
            }
            this._ksUpdateRemoveDomainIndexData(action, categ, params);
        } else {
            var index = $search_section.index();
            var domain_data = self.ks_dashboard_data.ks_dashboard_domain_data[model];
            domain_data.ks_domain_index_data.splice(index, 1);

            if (domain_data.ks_domain_index_data.length === 0) {
                $('.ks_dn_filter_section_container[data-ks-model-selector="'+ model + '"]').remove();
                delete self.ks_dashboard_data.ks_dashboard_domain_data[model];
                if(!Object.keys(self.ks_dashboard_data.ks_dashboard_domain_data).length){
                    $(".ks_dn_filter_applied_container").addClass('ks_hide');
                }
                }
//            } else {
//                $search_section.remove();
//            }

            domain_data['domain'] = self._ksMakeDomainFromDomainIndex(domain_data.ks_domain_index_data);
            domain_data['ks_remove'] = true
            self.state.pre_defined_filter = {}
            self.state.ksDateFilterSelection = 'none'
            self.state.custom_filter = {...domain_data}
            if(domain_data['domain'].length != 0){
                var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
                if(storedData !== null ){
                    this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
                }
                this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, self.ks_dashboard_data.ks_dashboard_domain_data, 1);
            }else{
                var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
                if(storedData){
                   this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
                }
            }

        }
    },

    ksGetParamsForItemFetch(item_id) {
        var self = this;
        var model1 = self.ks_dashboard_data.ks_item_model_relation[item_id][0];
        var model2 = self.ks_dashboard_data.ks_item_model_relation[item_id][1];

        if(model1 in self.ks_dashboard_data.ks_model_item_relation) {
            if (self.ks_dashboard_data.ks_model_item_relation[model1].indexOf(item_id)<0)
                self.ks_dashboard_data.ks_model_item_relation[model1].push(item_id);
        }else {
            self.ks_dashboard_data.ks_model_item_relation[model1] = [item_id];
        }

        if(model2 in self.ks_dashboard_data.ks_model_item_relation) {
            if (self.ks_dashboard_data.ks_model_item_relation[model2].indexOf(item_id)<0)
                self.ks_dashboard_data.ks_model_item_relation[model2].push(item_id);
        }else {
            self.ks_dashboard_data.ks_model_item_relation[model2] = [item_id];
        }

        var ks_domain_1 = self.ks_dashboard_data.ks_dashboard_domain_data[model1] && self.ks_dashboard_data.ks_dashboard_domain_data[model1]['domain'] || [];
        var ks_domain_2 = self.ks_dashboard_data.ks_dashboard_domain_data[model2] && self.ks_dashboard_data.ks_dashboard_domain_data[model2]['domain'] || [];

        return {
            ks_domain_1: ks_domain_1,
            ks_domain_2: ks_domain_2,
        }
    },

    ksRenderDashboard(){
        var self = this;
        super.ksRenderDashboard();
        var show_remove_option = false;
        if (Object.values(self.ks_dashboard_data.ks_dashboard_custom_domain_filter).length>0) self.ks_render_custom_filter(show_remove_option);
    },
    ks_render_custom_filter(show_remove_option){
        var self = this;
        var $container = $(renderToElement('ks_dn_custom_filter_input_container', {
                          ks_dashboard_custom_domain_filter: Object.values(this.ks_dashboard_data.ks_dashboard_custom_domain_filter),
                          show_remove_option: show_remove_option,
                          self: self

                          }));

        var first_field_select = Object.values(this.ks_dashboard_data.ks_dashboard_custom_domain_filter)[0]
        var field_type = first_field_select.type;
        var ks_operators = getDomainDisplayedOperators(first_field_select);
        var  operatorsinfo = ks_operators.map((x)=> getOperatorLabel(x));
        this.operators = ks_operators.map((val,index)=>{
            return{
                'symbol': val,
                'description': operatorsinfo[index]
            }

         })

        var operator_type = this.operators[0];
        var $operator_input = $(renderToElement('ks_dn_custom_domain_input_operator', {
                                    operators: this.operators,
                                    self:self
                                }));
        $container.append($operator_input);

        var $value_input = this._ksRenderCustomFilterInputSection(operator_type, ks_field_type[field_type], first_field_select.special_data)
        if ($value_input) $container.append($value_input);

        $("#ks_dn_custom_filters_container").append($container);
    },
    _ksRenderCustomFilterInputSection(operator_type, field_type, special_data){
        var $value_input;
        switch (field_type) {
            case 'boolean':
                return false;
                break;
            case 'selection':
                if (!operator_type) return false;
                else $value_input = $(renderToElement('ks_dn_custom_domain_input_selection', {
                                    selection_input: special_data['select_options'] || [],
                                }));
                break;
            case 'date':
            case 'datetime':
                if (!operator_type) return false;
                $value_input = this._ksRenderDateTimeFilterInput(operator_type, field_type);
                break;
            case 'char':
            case 'id':
            case 'number' :
                if (!operator_type) return false;
                else $value_input = $(renderToElement('ks_dn_custom_domain_input_text', {}));
                break;
            default:
                return;
        }
        return $value_input;
    },

    _ksRenderDateTimeFilterInput(operator, field_type){
        var self = this;
        var $value_container = $(renderToElement('ks_dn_custom_domain_input_date',{
            operator:operator,
            field_type:field_type,

        }));

        if (field_type == 'date'){
            $value_container.find("#datetimepicker1").each((index,item)=>{
                item.value = formatDate(DateTime.now(),{format: "yyyy-MM-dd" })
            })

        }else{
            $value_container.find("#datetimepicker1").each((index,item)=>{
                item.value = new Date(DateTime.now() + new Date().getTimezoneOffset() * -60 * 1000).toISOString().slice(0, 19)
            })
        }
        return $value_container;
    },

    ksOnCustomFilterApply(){
        var self = this;
        var model_domain = {};
        $('.ks_dn_custom_filter_input_container_section').each((index, filter_container) => {
            var field_id = $(filter_container).find('.ks_custom_filter_field_selector').val();
            var field_select = this.ks_dashboard_data.ks_dashboard_custom_domain_filter[field_id];
            var field_type = field_select.type;
            var domainValue = [];
            var domainArray = [];
            var operator = getDomainDisplayedOperators(field_select)[$(filter_container).find('.ks_operator_option_selector').prop('selectedIndex')];
            var ks_label = this.operators.filter((x) => x.symbol === operator)

            var label = field_select.name + ' ' + ks_label[0].description;
                if (['date', 'datetime'].includes(field_type)) {
                var dateValue = [];
                $(filter_container).find(".o_generator_menu_value .o_datepicker").each((index, $input_val) => {
                    var a = $($input_val).val();;
                    if (field_type === 'datetime'){
                        var b = formatDateTime(DateTime.fromISO(a),{ format: "yyyy-MM-dd HH:mm:ss" });
                        var c = formatDateTime(DateTime.fromISO(a),{ format: "dd/MM/yyyy HH:mm:ss" })  ;
                    }else{
                        var b = formatDate(DateTime.fromFormat(a,'yyyy-MM-dd'),{ format: "yyyy-MM-dd" });
                        var c = formatDate(DateTime.fromFormat(a,'yyyy-MM-dd'),{ format: "dd/MM/yyyy" });
                    }

                    domainValue.push(b);
                    dateValue.push(c);
                });
                label = label +' ' + dateValue.join(" and " );
            } else if (field_type === 'selection') {
                domainValue = [$(filter_container).find(".o_generator_menu_value").val()]
                label = label + ' ' + $(filter_container).find(".o_generator_menu_value").val();
            }
            else {
                domainValue = [$(filter_container).find(".o_generator_menu_value input").val()]
                label = label +' ' + $(filter_container).find(".o_generator_menu_value input").val();
            }

            if (operator === 'between') {
                domainArray.push(
                    [field_select.field_name, '>=', domainValue[0]],
                    [field_select.field_name, '<=', domainValue[1]]
                );
                domainArray.unshift('&');
            } else {
                domainArray.push([field_select.field_name, operator, domainValue[0]]);
            }

            if(field_select.model in model_domain){
                model_domain[field_select.model]['domain'] = model_domain[field_select.model]['domain'].concat(domainArray);
                model_domain[field_select.model]['domain'].unshift('|');
                model_domain[field_select.model]['label'] = model_domain[field_select.model]['label'] + ' or ' +  label;
            } else {
                model_domain[field_select.model] = {
                    'domain': domainArray,
                    'label': label,
                    'model_name': field_select.model_name,
                }
            }
        });
        this._ksAddCustomDomain(model_domain);
    },

    eraseCookie(name) {
    document.cookie = name + '=; Max-Age=-99999999; path=/';
    },

    setCookie(name, value, days) {
        var expires = "";
        if (days) {
            var date = new Date();
            date.setTime(date.getTime() + (days*24*60*60*1000));
            expires = "; expires=" + date.toUTCString();
        }
        document.cookie = name + "=" + (value || "") + expires + "; path=/";
    },

     setObjectInCookie(name, object, days) {
        var jsonString = JSON.stringify(object);
        this.setCookie(name, jsonString, days);
    },

    getCookie(name) {
        var nameEQ = name + "=";
        var ca = document.cookie.split(';');
        for (var i = 0; i < ca.length; i++) {
            var c = ca[i];
            while (c.charAt(0) == ' ') c = c.substring(1, c.length);
            if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
        }
        return null;
    },

    getObjectFromCookie(name) {
        var jsonString = this.getCookie(name);
        return jsonString ? JSON.parse(jsonString) : null;
    },

    _ksAddCustomDomain(model_domain){
        var self = this;
        $(".ks_dn_filter_applied_container").removeClass('ks_hide');
        Object.entries(model_domain).map(([model,val])=>{
            var domain_data = self.ks_dashboard_data.ks_dashboard_domain_data[model];
            var domain_index = {
                categ: false,
                domain: val['domain'],
                label: [val['label']],
                model: model,
            }

            if (domain_data) {
                domain_data.ks_domain_index_data.push(domain_index);
            } else {
                domain_data = {
                    'domain': [],
                    'model_name': val.model_name,
                    'item_ids': self.ks_dashboard_data.ks_model_item_relation[model],
                    'ks_domain_index_data': [domain_index],
                }
                self.ks_dashboard_data.ks_dashboard_domain_data[model] = domain_data;
            }

            $("#ks_dn_custom_filters_container").empty();
            var show_remove_option = false;
            self.ks_render_custom_filter(show_remove_option);

            domain_data['domain'] = self._ksMakeDomainFromDomainIndex(domain_data.ks_domain_index_data);
            self.state.custom_filter = {...domain_data}

            if(domain_data['domain'][0] !== undefined && domain_data['domain'].length != 0){
                var storedData = this.getObjectFromCookie('FilterOrderData' + self.ks_dashboard_id);
                if(storedData !== null ){
                    this.eraseCookie('FilterOrderData' + self.ks_dashboard_id);
                }
                this.setObjectInCookie('FilterOrderData' + self.ks_dashboard_id, self.ks_dashboard_data.ks_dashboard_domain_data, 1);
            }

            self.state.pre_defined_filter = {}
            self.state.ksDateFilterSelection = 'none'
        })
    },

    ksOnCustomFilterFieldSelect(ev){
        var self =this;
        var $parent_container = $(ev.currentTarget.parentElement);
        $parent_container.find('.ks_operator_option_selector').remove();
        $parent_container.find('.o_generator_menu_value').remove();
        var field_id = ev.currentTarget.value;
        var field_select = self.ks_dashboard_data.ks_dashboard_custom_domain_filter[field_id];
        var field_type = field_select.type;
        var ks_operators = getDomainDisplayedOperators(field_select);
        var  operatorsinfo = ks_operators.map((x)=> getOperatorLabel(x));
        this.operators = ks_operators.map((val,index)=>{
            return{
                'symbol': val,
                'description': operatorsinfo[index]
            }

         })
        var operator_type = self.operators[0];
        var $operator_input = $(renderToElement('ks_dn_custom_domain_input_operator', {
                                   operators: self.operators,
                                   self:self
                               }));

        $parent_container.append($operator_input);
        var $value_input = self._ksRenderCustomFilterInputSection(operator_type,  ks_field_type[field_type], field_select.special_data)
        if ($value_input) $parent_container.append($value_input);
    },
    ksOnCustomFilterOperatorSelect(ev){
        var $parent_container = $(ev.currentTarget.parentElement);
        var operator_symbol = ev.currentTarget.value;
        var field_id = $parent_container.find('.ks_custom_filter_field_selector').val();
        var field_select = this.ks_dashboard_data.ks_dashboard_custom_domain_filter[field_id];
        var field_type = field_select.type;
        var ks_operators = getDomainDisplayedOperators(field_select);
        var operator_type = ks_operators[ev.currentTarget.selectedIndex];

        $parent_container.find('.o_generator_menu_value').remove();
        var $value_input = this._ksRenderCustomFilterInputSection(operator_type, ks_field_type[field_type], field_select.special_data)
        if ($value_input) $parent_container.append($value_input);
    },

    ksOnCustomFilterConditionAdd(){
        var show_remove_option = true;
        this.ks_render_custom_filter(show_remove_option);
    },
    ksOnCustomFilterConditionRemove(ev){
        ev.stopPropagation();
        $(ev.currentTarget.parentElement).remove();
    },




});