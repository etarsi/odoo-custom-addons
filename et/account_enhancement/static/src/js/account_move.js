odoo.define('account_enhancement.TaxGroupComponent', function (require) {
    "use strict";

    const TaxGroupComponent = require('account.TaxGroupComponent');
    const session = require('web.session');
    const fieldUtils = require('web.field_utils');
    const { registry } = require('web.field_registry_owl');

    class TaxGroupComponentEnhancement extends TaxGroupComponent {
        _onChangeTaxValue() {
            // 1. Primero, tu lógica personalizada antes del super
            this.inputTax.el.value = this.inputTax.el.value.replace(',', '.');
            // 2. Llamas al método original
            super._onChangeTaxValue();
        }
    }

    // Registrar el componente extendido en el registry
    registry.category('fields').add('TaxGroupComponent', TaxGroupComponentEnhancement);

    // Si lo usas en un template personalizado, puedes darle otro nombre en el registry
    // registry.category('fields').add('tax_group_component_enhancement', TaxGroupComponentEnhancement);
});
