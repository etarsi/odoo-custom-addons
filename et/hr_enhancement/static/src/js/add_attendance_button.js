odoo.define('hr_enhancement.add_attendance_button', function (require) {
  'use strict';

  const ListController = require('web.ListController');
  const relationalFields = require('web.relational_fields');
  const core = require('web.core');
  const _t = core._t;

  function install(Controller) {
    Controller.include({
      renderButtons: function () {
        this._super.apply(this, arguments);

        // Contexto robusto
        const state = (this.model && this.model.get && this.model.get(this.handle, { raw: true })) || {};
        const ctx = Object.assign(
          {},
          state.context || {},
          this.context || {},
          (this.initialState && this.initialState.context) || {}
        );
        const modelName = state.model || this.modelName;

        // Mostrar el botón solo en hr.attendance y si la acción trae el flag
        if (modelName === 'hr.attendance' && (ctx.add_attendance_wizard_button || ctx.open_create_wizard)) {
          const self = this;
          const $btn = $('<button/>', {
            class: 'btn btn-secondary o_btn_attendance_wizard ml-2',
            text: _t('Nueva asistencia (modal)'),
          }).on('click', function (ev) {
            ev.preventDefault();
            self.do_action('hr_enhancement.action_hr_attendance_create_wizard');
          });

          if (this.$buttons && this.$buttons.length) {
            // Insertar al lado de "Crear"
            const $create = this.$buttons.find('.o_list_button_add');
            if ($create.length) {
              $create.after($btn);
            } else {
              // Fallback: agregar al contenedor de botones
              this.$buttons.append($btn);
            }
          }
        }
      },
    });
  }

  install(ListController);
  if (relationalFields && relationalFields.One2ManyListController) {
    install(relationalFields.One2ManyListController); // cubre sub-listas x2many
  }
});
