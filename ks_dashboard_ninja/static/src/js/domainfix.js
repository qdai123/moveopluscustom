/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import {RecordAutocomplete} from "@web/core/record_selectors/record_autocomplete";
import { _t } from "@web/core/l10n/translation";
import { Domain } from "@web/core/domain";
import {getFormat,DomainSelectorSingleAutocomplete,DomainSelectorAutocomplete} from "@web/core/tree_editor/tree_editor_autocomplete"

const SEARCH_LIMIT = 7;
const SEARCH_MORE_LIMIT = 320;

        //Patching to add uid and mycompany in dropdown
patch(RecordAutocomplete.prototype,{
   async loadOptionsSource(name) {
        if (this.env.services.action.currentController.action?.tag === "ks_dashboard_ninja"){
            if (this.lastProm) {
                this.lastProm.abort(false);
            }
            this.lastProm = this.search(name, SEARCH_LIMIT + 1);
            const nameGets = (await this.lastProm).map(([id, label]) => ([id, label ? label.split("\n")[0] : _t("Unnamed")]));
            this.addNames(nameGets);
            const options = nameGets.map(([value, label]) => ({value, label}));
            if (this.props.resModel !== 'res.company' &&  !this.props.ks_res_ids?.includes("%UID")){
                options.push({value:"%UID",label:"%UID"})
            }
            if (this.props.resModel === 'res.company' && !this.props.ks_res_ids?.includes("%MYCOMPANY")){
                options.push({value:"%MYCOMPANY",label:"%MYCOMPANY"})
            }
            if (SEARCH_LIMIT < nameGets.length) {
                options.push({
                    label: _t("Search More..."),
                    action: this.onSearchMore.bind(this, name),
                    classList: "o_m2o_dropdown_option",
                });
            }
            if (options.length === 0) {
                options.push({ label: _t("(no result)"), unselectable: true });
            }
            return options;
        }else{
            return await super.loadOptionsSource(...arguments);
        }
    },
});
RecordAutocomplete.props = {...RecordAutocomplete.props,ks_res_ids:{ type: Array,optional:true}};

 //Patching to remove invalid domain uid and mycompany from domain-modal
patch(DomainSelectorAutocomplete.prototype,{
     getTags(props, displayNames) {
        if (this.env.services.action.currentController.action?.tag === "ks_dashboard_ninja"){
            return props.resIds.map((val, index) => {
            const { text, colorIndex } = ksgetFormat(val, displayNames);
            return {
                text,
                colorIndex,
                onDelete: () => {
                    this.props.update([
                        ...this.props.resIds.slice(0, index),
                        ...this.props.resIds.slice(index + 1),
                    ]);
                },
            };
        });
        }else{
            return super.getTags(...arguments)
        }

    },
});
patch(DomainSelectorSingleAutocomplete.prototype,{
    getDisplayName(props = this.props, displayNames) {
        if (this.env.services.action.currentController.action?.tag === "ks_dashboard_ninja"){
        const { resId } = props;
        if (resId === false) {
            return "";
        }
        const { text } = ksgetFormat(resId, displayNames);
        return text;
    }else{
        return super.getDisplayName(...arguments)
    }
    },
});


export const ksgetFormat = (val, displayNames) => {
    let text;
    let colorIndex;
    if (val === '%UID'){
        return{text:'%UID',colorIndex:0}
    }else if (val === "%MYCOMPANY"){
        return{text:'%MYCOMPANY',colorIndex:0}
    }else{
        return getFormat(val,displayNames)
    }
};
