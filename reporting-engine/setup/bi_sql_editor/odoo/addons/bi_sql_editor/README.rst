=============
BI SQL Editor
=============

.. 
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! This file is generated by oca-gen-addon-readme !!
   !! changes will be overwritten.                   !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! source digest: sha256:0f7193c231739a0ede8ab9cbe51b73aa758543ffa31280d19a71578086d53a71
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Freporting--engine-lightgray.png?logo=github
    :target: https://github.com/OCA/reporting-engine/tree/15.0/bi_sql_editor
    :alt: OCA/reporting-engine
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/reporting-engine-15-0/reporting-engine-15-0-bi_sql_editor
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runboat-Try%20me-875A7B.png
    :target: https://runboat.odoo-community.org/builds?repo=OCA/reporting-engine&target_branch=15.0
    :alt: Try me on Runboat

|badge1| |badge2| |badge3| |badge4| |badge5|

This module extends the functionality of reporting, to support creation
of extra custom reports.
It allows user to write a custom SQL request. (Generally, admin users)

Once written, a new model is generated, and user can map the selected field
with odoo fields.
Then user ends the process, creating new menu, action and graph view.

Technically, the module create SQL View (or materialized view, if option is
checked). Materialized view duplicates datas, but request are fastest. If
materialized view is enabled, this module will create a cron task to refresh
the data).

By default, users member of 'SQL Request / User' can see all the views.
You can specify extra groups that have the right to access to a specific view.

Warning
-------
This module is intended for technician people in a company and for Odoo integrators.

It requires the user to know SQL syntax and Odoo models.

If you don't have such skills, do not try to use this module specially on a production
environment.

Use Cases
---------

this module is interesting for the following use cases

* You want to realize technical SQL requests, that Odoo framework doesn't allow
  (For exemple, UNION with many SELECT) A typical use case is if you want to have
  Sale Orders and PoS Orders datas in a same table

* You want to customize an Odoo report, removing some useless fields and adding
  some custom ones. In that case, you can simply select the fields of the original
  report (sale.report model for exemple), and add your custom fields

* You have a lot of data, and classical SQL Views have very bad performance.
  In that case, MATERIALIZED VIEW will be a good solution to reduce display duration

**Table of contents**

.. contents::
   :local:

Installation
============

* You must put this module as `server_wide_modules` in your odoo configuration file
  or add '--load=bi_sql_editor' if you start odoo in command line.

Configuration
=============

To configure this module, you need to:

* Go to Settings / Technical / Database Structure / SQL Views

* tip your SQL request

  .. figure:: https://raw.githubusercontent.com/OCA/reporting-engine/15.0/bi_sql_editor/static/description/01_sql_request.png
     :width: 800 px

* Select the group(s) that could have access to the view

  .. figure:: https://raw.githubusercontent.com/OCA/reporting-engine/15.0/bi_sql_editor/static/description/02_security_access.png
     :width: 800 px

* Click on the button 'Clean and Check Request'

* Once the sql request checked, the module analyses the column of the view,
  and propose field mapping. For each field, you can decide to create an index
  and set if it will be displayed on the pivot graph as a column, a row or a
  measure.

  .. figure:: https://raw.githubusercontent.com/OCA/reporting-engine/15.0/bi_sql_editor/static/description/03_field_mapping.png
     :width: 800 px

* Click on the button 'Create SQL View, Indexes and Models'. (this step could
  take a while, if view is materialized)

* If it's a MATERIALIZED view:

    * a cron task is created to refresh
      the view. You can so define the frequency of the refresh.
    * the size of view (and the indexes is displayed)

  .. figure:: https://raw.githubusercontent.com/OCA/reporting-engine/15.0/bi_sql_editor/static/description/04_materialized_view_setting.png
     :width: 800 px

* Finally, click on 'Create UI', to create new menu, action, graph view and
  search view.

Usage
=====

To use this module, you need to:

#. Go to 'Reporting' / 'Custom Reports'

#. Select the desired report

  .. figure:: https://raw.githubusercontent.com/OCA/reporting-engine/15.0/bi_sql_editor/static/description/05_reporting_pivot.png
     :width: 800 px

* You can switch to 'Pie' chart or 'Line Chart' as any report,

  .. figure:: https://raw.githubusercontent.com/OCA/reporting-engine/15.0/bi_sql_editor/static/description/05_reporting_pie.png
     :width: 800 px

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/reporting-engine/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
`feedback <https://github.com/OCA/reporting-engine/issues/new?body=module:%20bi_sql_editor%0Aversion:%2015.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
~~~~~~~

* GRAP

Contributors
~~~~~~~~~~~~

* Sylvain LE GAL (https://twitter.com/legalsylvain)
* Richard deMeester, WilldooIT (http://www.willdooit.com/)
* David James, WilldooIT (http://www.willdooit.com/)

* This module is highly inspired by the work of
    * Onestein: (http://www.onestein.nl/)
      Module: OCA/server-tools/bi_view_editor.
      Link: https://github.com/OCA/reporting-engine/tree/9.0/bi_view_editor
    * Anybox: (https://anybox.fr/)
      Module : OCA/server-tools/materialized_sql_view
      link: https://github.com/OCA/server-tools/pull/110
    * GRAP, Groupement Régional Alimentaire de Proximité: (http://www.grap.coop/)
      Module: grap/odoo-addons-misc/pos_sale_reporting
      link: https://github.com/grap/odoo-addons-misc/tree/7.0/pos_sale_reporting

Maintainers
~~~~~~~~~~~

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

.. |maintainer-legalsylvain| image:: https://github.com/legalsylvain.png?size=40px
    :target: https://github.com/legalsylvain
    :alt: legalsylvain

Current `maintainer <https://odoo-community.org/page/maintainer-role>`__:

|maintainer-legalsylvain| 

This module is part of the `OCA/reporting-engine <https://github.com/OCA/reporting-engine/tree/15.0/bi_sql_editor>`_ project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.
