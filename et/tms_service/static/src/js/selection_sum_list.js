odoo.define('tms_service.SelectionSumList', function (require) {
    "use strict";

    var ListController = require('web.ListController');
    var ListView = require('web.ListView');
    var viewRegistry = require('web.view_registry');
    var core = require('web.core');
    var _t = core._t;

    var SelectionSumController = ListController.extend({

        renderButtons: function () {
            this._super.apply(this, arguments);
            if (this.$buttons) {
                this.$selectionSum = $('<span/>', {
                    class: 'o_selection_sum ml-2',
                    text: _t('Total cantidad: 0'),
                });
                this.$buttons.append(this.$selectionSum);
                // o si querés solo en el bloque de botones de lista:
                // this.$buttons.find('.o_list_buttons').append(this.$selectionSum);
            }
        },

        // 🔹 ESTE ES EL QUE IMPORTA
        _onSelectionChanged: function (event) {
            this._super.apply(this, arguments);
            this._computeSelectionSum();
        },

        _computeSelectionSum: function () {
            var self = this;
            var ids = this.getSelectedIds();

            if (!this.$selectionSum) {
                return;
            }
            if (!ids.length) {
                this.$selectionSum.text(_t('Total cantidad: 0'));
                return;
            }

            // ⚠️ CAMBIÁ 'cantidad_d' POR EL NOMBRE REAL DEL CAMPO
            this._rpc({
                model: this.modelName,
                method: 'read',
                args: [ids, ['cantidad_bultos']],
            }).then(function (records) {
                var total = 0;
                records.forEach(function (rec) {
                    total += rec.cantidad_bultos || 0;
                });
                self.$selectionSum.text(_t('Total cantidad: ') + total);
            });
        },
    });

    var SelectionSumListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: SelectionSumController,
        }),
    });

    viewRegistry.add('selection_sum_list', SelectionSumListView);
});
