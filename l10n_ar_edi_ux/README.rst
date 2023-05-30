.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

===================================
Argentinian Electronic Invoicing UX
===================================

* Disable l10n_ar_ux view that add Argentinian Localization accounting settings and use the one added by l10n_ar_edi
* Logic to connecto to AFIP Padron using connection approach in enterprise module l10n_ar_edi

About Padron:

#. If you want to disable Title Case for afip retrived data, you can change or create a paremeter "use_title_case_on_padron_afip" with value False (by default title case is used)
#. para actualizar tenemos básicamente dos opciones:

    * Desde un partner cualquiera, si el mismo tiene configurado CUIT, entonces puede hacer click en el botón "Actualizar desde AFIP"
    * Hacerlo masivamente desde ""

#. Si estas en un ambiente de testing pueden utilizar estos CUITs de prueba para el padrón 'ws_sr_padron_a5' https://gist.github.com/zaoral/245ea456c53aef5c8d2f12a099d30909

Installation
============

To install this module, you need to:

#. Nothing to do

Configuration
=============

To configure this module, you need to:

#. Nothing to do

Usage
=====

To use this module, you need to:

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: http://runbot.adhoc.com.ar/

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/odoo-argentina/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed feedback.

Credits
=======

Images
------

* |company| |icon|

Contributors
------------

Maintainer
----------

|company_logo|

This module is maintained by the |company|.

To contribute to this module, please visit https://www.adhoc.com.ar.
