odoo.define('tms_service.SelectionSumList', function (require) {
    "use strict";

    var ListController = require('web.ListController');
    var ListView = require('web.ListView');
    var viewRegistry = require('web.view_registry');
    var core = require('web.core');
    var fieldUtils = require('web.field_utils');
    var _t = core._t;

    var SelectionSumController = ListController.extend({

        renderButtons: function () {
            this._super.apply(this, arguments);

            if (this.$buttons) {
                // Contenedor tipo “chip”
                this.$selectionSum = $('<span/>', {
                    class: 'badge badge-info o_selection_sum ml-2 px-3 py-2',
                }).css({
                    'font-size': '14px',
                    'font-weight': '600',
                }).hide();  // 🔸 por defecto oculto

                // Campo 1
                this.$sumCampo1 = $('<span/>', {
                    class: 'mr-3',
                    text: _t('T. Bultos: 0'),
                });

                // Campo 2
                this.$sumCampo2 = $('<span/>', {
                    text: _t('T. Facturado: 0'),
                });

                this.$selectionSum
                    .append(this.$sumCampo1)
                    .append(this.$sumCampo2);

                // Lo ponemos al lado de "Crear"
                var $addBtn = this.$buttons.find('.o_list_button_add');
                if ($addBtn.length) {
                    $addBtn.after(this.$selectionSum);
                } else {
                    this.$buttons.append(this.$selectionSum);
                }
            }
        },

        _onSelectionChanged: function (event) {
            this._super.apply(this, arguments);
            this._computeSelectionSum();
        },

        _resetSums: function () {
            if (!this.$selectionSum) {
                return;
            }
            this.$sumCampo1.text(_t('T. Bultos: 0'));
            this.$sumCampo2.text(_t('T. Facturado: 0'));
            this.$selectionSum.hide();   // 🔸 al resetear, lo oculto
        },

        _computeSelectionSum: function () {
            var self = this;
            var ids = this.getSelectedIds();

            if (!this.$selectionSum) {
                return;
            }
            if (!ids.length) {
                this._resetSums();   // 🔸 sin selección → oculto
                return;
            }

            // hay selección → lo muestro
            this.$selectionSum.show();

            this._rpc({
                model: this.modelName,
                method: 'read',
                args: [ids, ['cantidad_bultos', 'amount_totals']],
            }).then(function (records) {
                var total1 = 0;
                var total2 = 0;

                records.forEach(function (rec) {
                    total1 += rec.cantidad_bultos || 0;   // campo 1
                    total2 += rec.amount_totals || 0;     // campo 2
                });

                self.$sumCampo1.text(
                    _t('T. Bultos: ') +
                    fieldUtils.format.float(total1, {digits: [16, 2]})
                );

                self.$sumCampo2.text(
                    _t('T. Facturado: ') +
                    fieldUtils.format.float(total2, {digits: [16, 2]})
                );
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
