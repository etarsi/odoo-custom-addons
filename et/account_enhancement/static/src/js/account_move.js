odoo.define('account_enhancement.TaxTotalsComponent', function (require) {
    "use strict";

    const TaxTotalsComponent = require('account.TaxTotalsComponent');
    const session = require('web.session');
    const fieldUtils = require('web.field_utils');
    const { registry } = require('web.field_registry_owl');

    class TaxTotalsComponentEnhancement extends TaxTotalsComponent {
        _onChangeTaxValueByTaxGroup(ev) {
            console.log('TaxTotalsComponentEnhancement: _onChangeTaxValueByTaxGroup called');
            console.log('Event:', this.totals.value);
            this.trigger('field-changed', {
                dataPointID: this.record.id,
                changes: { tax_totals_json: JSON.stringify(this.totals.value) }
            })
        }
    }

    // Registrar el componente extendido en el registry
    registry.category('fields').add('TaxTotalsComponent', TaxTotalsComponentEnhancement);

    // Si lo usas en un template personalizado, puedes darle otro nombre en el registry
    // registry.category('fields').add('tax_group_component_enhancement', TaxGroupComponentEnhancement);
});
