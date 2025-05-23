============================
Brand External Report Layout
============================

.. 
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! This file is generated by oca-gen-addon-readme !!
   !! changes will be overwritten.                   !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! source digest: sha256:6106bf014eb59995b9036a39bade85912de6f0a30c2dd9f56cf2114617a026a5
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Fbrand-lightgray.png?logo=github
    :target: https://github.com/OCA/brand/tree/15.0/brand_external_report_layout
    :alt: OCA/brand
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/brand-15-0/brand-15-0-brand_external_report_layout
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runboat-Try%20me-875A7B.png
    :target: https://runboat.odoo-community.org/builds?repo=OCA/brand&target_branch=15.0
    :alt: Try me on Runboat

|badge1| |badge2| |badge3| |badge4| |badge5|

This module allows you to have a different layout by brand for your external
reports.

**Table of contents**

.. contents::
   :local:

Usage
=====

To use this module, you need to:

#. Go to Settings > Users & Companies > Brands
#. Add a new brand or select an existing one
#. Enter brand information and select the a layout
#. Go to any branded object abd print the PDF report. It includes the information of the brand.

Known issues / Roadmap
======================

To simplify the customization of the external layout we replaced the variable
company that odoo compute in the external_layout view by the object brand.

With this module, all custom layouts will display brand information out of the box.

This was possible and easy to implement as the company and the brand models
inherit from partner model and share the same informational fields.

The computed variable company is used to set report header and footer. It's not
meant to be used in the report business logic itself. But in that case
(if a custom layout use the variable company for some-reason other then header
and footer) this module can cause an issue because the used field can be
missing in the brand model or not correctly set.

In this case, we recommend to always use document field company for this use-end.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/brand/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
`feedback <https://github.com/OCA/brand/issues/new?body=module:%20brand_external_report_layout%0Aversion:%2015.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
~~~~~~~

* ACSONE SA/NV

Contributors
~~~~~~~~~~~~

* Souheil Bejaoui <souheil.bejaoui@acsone.eu>

* `Landoo, Sistemas de Información, S.L. <https://www.landoo.es>`_:

  * Vicent Cubells <vicent@vcubells.net>
* Freni Patel <fpatel@opensourceintegrators.com>

Maintainers
~~~~~~~~~~~

This module is maintained by the OCA.

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

.. |maintainer-sbejaoui| image:: https://github.com/sbejaoui.png?size=40px
    :target: https://github.com/sbejaoui
    :alt: sbejaoui

Current `maintainer <https://odoo-community.org/page/maintainer-role>`__:

|maintainer-sbejaoui| 

This module is part of the `OCA/brand <https://github.com/OCA/brand/tree/15.0/brand_external_report_layout>`_ project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.
