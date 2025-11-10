odoo.define('hr_enhancement.tree_button', function (require) { 
  "use strict"; 

  var ListController = require('web.ListController'); 
  var ListView = require('web.ListView'); 
  var viewRegistry = require('web.view_registry'); 
  var AttendanceListController = ListController.extend({ 
   buttons_template: 'button_near_create.buttons', 

    events: _.extend({}, ListController.prototype.events, { 
      'click.open_wizard_button': '_openWizard', 
    }), 

    _openWizard: function (ev) { 
      var self = this;
      this.do_action({
        type: 'ir.actions.act_window',
        res_model: 'hr.attendance.create.wizard',
        name: 'Registrar Asistencia',
        views: [[false, 'form']],
        view_mode: 'form',
        view_type: 'form',
        target: 'new',
        res_id: false
      });
    },
  }); 

  const AttendanceListView = ListView.extend({ 
    config: _.extend({}, ListView.prototype.config, { 
      Controller: AttendanceListController, 
    }), 
  }); 

  viewRegistry.add('button_in_tree', AttendanceListView); 
});
