odoo.define('hr_enhancement.open_create_wizard', function (require) {
  'use strict';

  const ListController = require('web.ListController');
  const relationalFields = require('web.relational_fields');
  const One2ManyListController = relationalFields.One2ManyListController;

  function installHook(Controller) {
    Controller.include({
      renderButtons: function () {
        this._super.apply(this, arguments);

        // Estado/contexto robusto (action + controller + modelo)
        const state = (this.model && this.model.get && this.model.get(this.handle, { raw: true })) || {};
        const ctx = Object.assign(
          {},
          state.context || {},
          this.context || {},
          (this.initialState && this.initialState.context) || {}
        );
        const modelName = state.model || this.modelName;

        // Solo para hr.attendance y cuando el action traiga el flag
        if (modelName === 'hr.attendance' && ctx.open_create_wizard) {
          const self = this;
          // Desenganchar handler default y enganchar el nuestro
          this.$buttons.off('click', '.o_list_button_add');
          this.$buttons.on('click', '.o_list_button_add', function (ev) {
            ev.preventDefault();
            ev.stopImmediatePropagation();
            self.do_action('hr_enhancement.action_hr_attendance_create_wizard');
          });
        }
      },
    });
  }

  installHook(ListController);
  if (One2ManyListController) {
    installHook(One2ManyListController);
  }
});
