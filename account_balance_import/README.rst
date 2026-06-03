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


Account Balance Import
======================
Este módulo extiende la funcionalidad de importación de saldos iniciales contables, proporcionando una interfaz mejorada en la configuración de contabilidad.

Características principales:

* **Revisión de Datos de Empresa (Review Company Data)**: Permite revisar y confirmar la información de la compañía antes de iniciar el proceso de importación.

* **Configuración de Períodos (Set Periods)**: Facilita la configuración de años fiscales y períodos contables necesarios para la importación.

* **Importación de Saldos de Partners (Partners Balance)**: Importa saldos iniciales de partners (deudores por ventas, proveedores y otras cuentas a cobrar o a pagar). Se generan los asientos contables correspondientes y las deudas quedan correctamente vinculadas.

* **Revisión de Plan de Cuentas (Chart of Accounts)**: Permite revisar el plan de cuentas y configurar los saldos de fin de año para cada cuenta contable.

El módulo reorganiza la interfaz de importación en la configuración de contabilidad, dividiendo las opciones en dos secciones:
- **Initial Setup** (izquierda): Configuración inicial de empresa y períodos
- **Importación de Datos** (derecha): Importación de saldos de partners y cuentas contables


Usage
=====

Para utilizar este módulo:

1. Vaya a Contabilidad > Configuración > Ajustes
2. En la sección "Accounting Import" encontrará las opciones organizadas:

   **Initial Setup:**

   - Review Company Data: Verifique los datos de su empresa
   - Set Periods: Configure años fiscales y períodos

   **Importación:**

   - Partners Balance: Importe saldos iniciales de partners
   - Chart of Accounts: Revise su plan de cuentas e importe saldos contables


Bug Tracker
===========


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
