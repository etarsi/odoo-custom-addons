odoo.define('hr_enhancement.tree_button', function (require) { 
  "use strict"; 

  var ListController = require('web.ListController'); 
  var ListView = require('web.ListView'); 
  var viewRegistry = require('web.view_registry'); 

  function hrAttendance() {
    if (this.$buttons) {
        var self = this;
        this._({
            model: "sale",
            method: "action_open_sale_order",
            args: [false, {new_order: true}],
            context: {calendar_summary_id: calendar_summary_id || false},
        }).then(function (action) {
            self.$buttons.on("click", ".o_button_new_sale_order", function () {
                self.do_action(action);
            });
        });
    }
}

  var AttendanceListController = ListController.extend({ 
    buttons_template: 'hr_enhancement.buttons', 

    events: _.extend({}, ListController.prototype.events, { 
      'click .open_wizard_button': '_openAttendanceWizard', 
    }), 

    _openAttendanceWizard: function (ev) { 
      ev.preventDefault();
      const state = (this.model && this.model.get && this.model.get(this.handle, { raw: true })) || {};
      const model = state.model || this.modelName;
      if (model !== 'hr.attendance') {
        return;
      }
      this.do_action('hr_enhancement.hr_attendance_create_wizard_action');
    },
  }); 

  const AttendanceListView = ListView.extend({ 
    config: _.extend({}, ListView.prototype.config, { 
      Controller: AttendanceListController, 
    }), 
  }); 

  viewRegistry.add('o_hr_attendance_eventual_tree', AttendanceListView); 
});
