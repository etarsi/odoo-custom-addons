=====
Brand
=====

.. 
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! This file is generated by oca-gen-addon-readme !!
   !! changes will be overwritten.                   !!
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
   !! source digest: sha256:965f40451d83262dd525a4b5fb3a75e32d551bc21058d414de312d7709a35c25
   !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-OCA%2Fbrand-lightgray.png?logo=github
    :target: https://github.com/OCA/brand/tree/15.0/brand
    :alt: OCA/brand
.. |badge4| image:: https://img.shields.io/badge/weblate-Translate%20me-F47D42.png
    :target: https://translation.odoo-community.org/projects/brand-15-0/brand-15-0-brand
    :alt: Translate me on Weblate
.. |badge5| image:: https://img.shields.io/badge/runboat-Try%20me-875A7B.png
    :target: https://runboat.odoo-community.org/builds?repo=OCA/brand&target_branch=15.0
    :alt: Try me on Runboat

|badge1| |badge2| |badge3| |badge4| |badge5|

This is a base addon for brand modules. It adds the brand object and its menu and
define an abstract model to be inherited from branded objects.

**Table of contents**

.. contents::
   :local:

Usage
=====

To use this module, you need to:

#. Go to Settings > General Settings
#. Select the brand use level
#. Go to Settings > Users & Companies > Brands
#. Add a new brand
#. Install one of branding module (e.g. account_brand)
#. Based on your choice for the brand use level, you will see a new field added to the
   branded object

To make a branded object, you need to:

#. Inherit from the `res.brand.mixin`
    .. code-block:: python


        class YourModel(models.Model):
            _name = 'your.model'
            _inherit = ['your.model', 'res.brand.mixin']

#. Add the brand field to the object form or tree view. The mixin will add the brand
   use level field automatically to the view and set the modifiers to the brand field.
   This will define its visibility and if it's required or not.

You can refer to the `account_brand <https://github.com/OCA/brand/blob/12.0/account_brand>`_. for more details.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues <https://github.com/OCA/brand/issues>`_.
In case of trouble, please check there if your issue has already been reported.
If you spotted it first, help us to smash it by providing a detailed and welcomed
`feedback <https://github.com/OCA/brand/issues/new?body=module:%20brand%0Aversion:%2015.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
~~~~~~~

* ACSONE SA/NV

Contributors
~~~~~~~~~~~~

* Souheil Bejaoui <souheil.bejaoui@acsone.eu>

* `Obertix <https://www.obertix.net>`_:

  * Vicent Cubells
* Ammar Officewala <aofficewala@opensourceintegrators.com>

Other credits
~~~~~~~~~~~~~

* ACSONE SA/NV <https://www.acsone.eu>

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

This module is part of the `OCA/brand <https://github.com/OCA/brand/tree/15.0/brand>`_ project on GitHub.

You are welcome to contribute. To learn how please visit https://odoo-community.org/page/Contribute.
