odoo.define('hr_enhancement.attendance_list_buttons', function (require) {
  'use strict';
  const ListController = require('web.ListController');

  ListController.include({
    events: Object.assign({}, ListController.prototype.events, {
      'click .o_btn_attendance_wizard': '_openAttendanceWizard',
    }),

    _openAttendanceWizard: function (ev) {
      ev.preventDefault();
      const state = (this.model && this.model.get && this.model.get(this.handle, { raw: true })) || {};
      const model = state.model || this.modelName;
      if (model !== 'hr.attendance') {
        return;
      }
      this.do_action('hr_enhancement.action_hr_attendance_create_wizard');
    },
  });
});
