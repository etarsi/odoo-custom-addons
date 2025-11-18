/** @odoo-module **/

import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { Component } from "@odoo/owl";

class RowNumberField extends Component {
    get value() {
        // this.props.record es el registro actual de la fila
        const record = this.props.record;
        const list = record.list;  // la lista a la que pertenece
        const index = list.records.indexOf(record);
        return index >= 0 ? index + 1 : "";
    }
}

RowNumberField.template = "your_module.RowNumberField";
RowNumberField.props = standardFieldProps;
RowNumberField.supportedTypes = ["integer", "many2one", "char", "float"]; 

registry.category("fields").add("row_number", RowNumberField);
