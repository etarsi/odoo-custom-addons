odoo.define('hr_enhancement.attendance_create_wizard', function (require) {
    'use strict';
    const ListController = require('web.ListController');

    ListController.include({
        createRecord: function () {
            const ctx = (this.initialState && this.initialState.context) || {};
            console.log("Contexto en createRecord:", ctx);
            if (this.modelName === 'hr.attendance' && ctx.open_create_wizard) {
                return this.do_action('hr_enhancement.action_hr_attendance_create_wizard');
            }
                return this._super.apply(this, arguments);
            },
    });
});
