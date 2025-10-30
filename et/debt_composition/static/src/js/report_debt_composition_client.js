odoo.define('debt_composition.rdcc_reload_patch', function (require) {
    "use strict";

    const ListController = require('web.ListController');

    const _reload = ListController.prototype.reload;

    ListController.include({
        reload: function () {
            if (this.modelName !== 'report.debt.composition.client') {
                return _reload.apply(this, arguments);
            }
            const args = arguments;
            const self = this;
            return this._rpc({
                model: 'report.debt.composition.client',
                method: 'action_refresh_sql',
                args: [],        
            }).then(
                function () { return _reload.apply(self, args); },
                function () { return _reload.apply(self, args); }
            );
        },
    });
});
