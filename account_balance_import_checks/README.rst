.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

#. Nothing to configure


Account Balance Import - Checks
================================

Este módulo extiende la funcionalidad de `account_balance_import` para permitir la importación de cheques
(cheques de terceros en cartera y cheques propios emitidos) como parte de la carga de saldos iniciales.

Se integra con el módulo `l10n_latam_check` para gestionar correctamente los cheques según las
regulaciones de LATAM.

Características principales:

* Importación de cheques de terceros en cartera
* Importación de cheques propios emitidos pero no debitados
* Generación automática de asientos contables
* Integración con el sistema de cheques de LATAM

Usage
=====

Para importar cheques:

#. Ir a Contabilidad > Configuración > Importar Saldos Iniciales
#. Seleccionar la plantilla de cheques
#. Completar la información requerida en la plantilla Excel
#. Importar el archivo

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/enterprise-extensions/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed
`feedback <https://github.com/ingadhoc/enterprise-extensions/issues/new?body=module:%20
account_balance_import_checks%0Aversion:%20
19.0%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Do not contact contributors directly about support or help with technical issues.

Credits
=======

Authors
~~~~~~~

* |company|

Contributors
~~~~~~~~~~~~

* |company| |icon|

Maintainer
~~~~~~~~~~

* |company_logo|

This module is maintained by ADHOC SA.

To contribute to this module, please visit https://www.adhoc.com.ar.
