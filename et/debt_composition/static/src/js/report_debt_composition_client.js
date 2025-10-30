odoo.define('debt_composition.rdcc_reload_patch', function (require) {
    "use strict";

    var ListController = require('web.ListController');

    ListController.include({
        reload: function () {
            if (this.modelName === 'report.debt.composition.client') {
                var self = this;
                return this._rpc({
                    model: 'report.debt.composition.client',
                    method: 'action_refresh_sql',
                    args: [],
                }).then(function () {
                    return self._super.apply(self, arguments);
                });
            }
            return this._super.apply(this, arguments);
        },
    });
});
