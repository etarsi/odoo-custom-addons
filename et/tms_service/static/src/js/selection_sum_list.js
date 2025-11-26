odoo.define('tms_service.SelectionSumList', function (require) {
    'use strict';

    const core = require('web.core');
    const ListController = require('web.ListController');
    const ListView = require('web.ListView');
    const viewRegistry = require('web.view_registry');
    const _t = core._t;

    const SelectionSumController = ListController.extend({
        /**
         * Agrego un texto en la barra de botones (donde están Acción, Filtros, etc.)
         */
        renderButtons: function () {
            this._super.apply(this, arguments);
            if (this.$buttons) {
                this.$selectionSum = $('<span/>', {
                    class: 'o_selection_sum ml-2',
                    text: _t('Total cantidad: 0'),
                });
                this.$buttons.append(this.$selectionSum);
            }
        },

        /**
         * Cada vez que cambia la selección, recalculo el total.
         */
        _updateSelection: function () {
            this._super.apply(this, arguments);
            this._computeSelectionSum();
        },

        _computeSelectionSum: function () {
            const ids = this.getSelectedIds();
            const self = this;

            if (!this.$selectionSum) {
                return;
            }
            if (!ids.length) {
                this.$selectionSum.text(_t('Total cantidad: 0'));
                return;
            }

            // OJO: cambiá 'cantidad_d' por el nombre real del campo cantidad de tu modelo
            this._rpc({
                model: this.modelName,
                method: 'read',
                args: [ids, ['cantidad_bultos']],
            }).then(function (records) {
                let total = 0;
                records.forEach(function (rec) {
                    total += rec.cantidad_bultos || 0;
                });

                self.$selectionSum.text(
                    _.str.sprintf(
                        _t('Total cantidad seleccionada: %s'),
                        total
                    )
                );
            });
        },
    });

    const SelectionSumListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: SelectionSumController,
        }),
    });

    // nombre que vas a usar en el js_class del <tree>
    viewRegistry.add('selection_sum_list', SelectionSumListView);
});
