odoo.define('hr_enhancement.attendance_list_button', function (require) {
  'use strict';
  const ListController = require('web.ListController');
  const relationalFields = require('web.relational_fields');

  function install(Controller) {
    Controller.include({
      renderButtons() {
        this._super.apply(this, arguments);

        // Estado/contexto “robusto”
        const state = (this.model && this.model.get && this.model.get(this.handle, { raw: true })) || {};
        const ctx   = Object.assign({}, state.context || {}, this.context || {}, (this.initialState && this.initialState.context) || {});
        const model = state.model || this.modelName;

        // Si no estamos en hr.attendance o no viene el flag, ocultamos el botón
        const $btn = this.$buttons && this.$buttons.find('.o_btn_attendance_wizard');
        if (!$btn || !$btn.length) return;

        if (model !== 'hr.attendance' || !ctx.add_attendance_wizard_button) {
          $btn.hide();
          return;
        }

        // Click -> abrir wizard en modal
        $btn.off('click').on('click', (ev) => {
          ev.preventDefault();
          this.do_action('hr_enhancement.action_hr_attendance_create_wizard');
        });
      },
    });
  }

  install(ListController);
  if (relationalFields && relationalFields.One2ManyListController) {
    install(relationalFields.One2ManyListController); // también cubre x2many
  }
});
