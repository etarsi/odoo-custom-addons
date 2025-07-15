odoo.define('account_enhancement.TaxGroupComponent', function (require) {
    "use strict";

    const TaxGroupComponent = require('account.TaxGroupComponent');
    const { patch } = require('web.utils');
    
    // Puedes usar patch para sobreescribir métodos OWL de forma segura
    patch(TaxGroupComponent.prototype, 'account_enhancement_TaxGroupComponent_patch', {
        /**
         * Override _onChangeTaxValue se cambia el comportamiento del inpunt sobre el punto a coma decimal
        **/

        _onChangeTaxValue() {
            this.setState('disable'); // Disable the input
            let newValue = this.inputTax.el.value.replace(',', '.'); // Get the new value
            console.log('newValue', newValue);
            let currency = session.get_currency(this.props.record.data.currency_id.data.id); // The records using this widget must have a currency_id field.
            try {
                newValue = fieldUtils.parse.float(newValue); // Need a float for format the value
                newValue = fieldUtils.format.float(newValue, null, {digits: currency.digits}); // Return a string rounded to currency precision
                newValue = fieldUtils.parse.float(newValue); // Convert back to Float to compare with oldValue to know if value has changed
            } catch (err) {
                $(this.inputTax.el).addClass('o_field_invalid');
                this.setState('edit');
                return;
            }
            // The newValue can't be equals to 0
            if (newValue === this.props.taxGroup.tax_group_amount || newValue === 0) {
                this.setState('readonly');
                return;
            }
            this.props.taxGroup.tax_group_amount = newValue;
            this.trigger('change-tax-group', {
                oldValue: this.props.taxGroup.tax_group_amount,
                newValue: newValue,
                taxGroupId: this.props.taxGroup.tax_group_id
            });
        }
    });
});
