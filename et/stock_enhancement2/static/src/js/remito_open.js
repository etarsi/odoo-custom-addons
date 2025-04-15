odoo.define('stock_enhancement2.remito_open', function (require) {
    "use strict";

    const AbstractAction = require('web.AbstractAction');
    const core = require('web.core');

    const OpenRemitoTabs = AbstractAction.extend({
        start: function () {
            const urls = this.params.urls || [];
            urls.forEach((url, i) => {
                setTimeout(() => {
                    window.open(url, '_blank');
                }, i * 300);
            });
            return Promise.resolve();
        },
    });

    core.action_registry.add('reload_and_open_remitos', OpenRemitoTabs);
    return OpenRemitoTabs;
});