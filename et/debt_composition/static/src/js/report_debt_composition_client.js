odoo.define('debt_composition.rdcc_reload_patch', function (require) {
    "use strict";

    const ListController = require('web.ListController');
    const _reload = ListController.prototype.reload;

    ListController.include({
        init: function () {
            this._super.apply(this, arguments);
            this.__rdccRefreshing = false;
        },
        reload: function () {
            if (this.modelName !== 'report.debt.composition.client') {
                return _reload.apply(this, arguments);
            }
            if (this.__rdccRefreshing) {
                return _reload.apply(this, arguments);
            }
            this.__rdccRefreshing = true;

            const args = arguments;
            const self = this;

            return this._rpc({
                model: 'report.debt.composition.client',
                method: 'action_refresh_sql',
                args: [],
                kwargs: {},
            }).then(function () {
                self.__rdccRefreshing = false;
                return _reload.apply(self, args);
            }, function () {
                self.__rdccRefreshing = false;
                return _reload.apply(self, args);
            });
        },
    });
});
