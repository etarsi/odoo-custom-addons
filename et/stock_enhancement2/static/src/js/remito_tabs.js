odoo.define('stock_enhancement2.remito_tabs', function (require) {
    "use strict";

    const AbstractAction = require('web.AbstractAction');
    const core = require('web.core');

    const OpenRemitoTabs = AbstractAction.extend({
        start: function () {
            const urls = this.params.urls || [];
            urls.forEach(function (url, index) {
                setTimeout(() => {
                    window.open(url, '_blank');
                }, index * 300);
            });
            return Promise.resolve();
        },
    });

    core.action_registry.add('open_remito_tabs', OpenRemitoTabs);

    return OpenRemitoTabs;
});
