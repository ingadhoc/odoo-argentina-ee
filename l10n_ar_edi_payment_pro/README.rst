===================================
Account Payment Pro for l10n_ar_edi
===================================

.. |badge1| image:: https://img.shields.io/badge/maturity-Beta-yellow.png
    :target: https://odoo-community.org/page/development-status
    :alt: Beta
.. |badge2| image:: https://img.shields.io/badge/licence-AGPL--3-blue.png
    :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
    :alt: License: AGPL-3
.. |badge3| image:: https://img.shields.io/badge/github-ADHOC--SA-lightgray.png?logo=github
    :target: https://github.com/ADHOC-SA/odoo-argentina-ee
    :alt: ADHOC-SA/odoo-argentina-ee

|badge1| |badge2| |badge3|

Este módulo extiende la funcionalidad de **Account Payment Pro** para integrarla con la facturación electrónica argentina (**l10n_ar_edi**).

**Funcionalidades Principales**
-------------------------------

* Agrega campos específicos de ARCA para el período de asociación en el wizard de pagos
* Permite seleccionar facturas de origen para notas de crédito y débito automáticas
* Configura automáticamente los períodos de asociación ARCA para notas de débito generadas por recargos financieros automáticos
* Filtrado inteligente de facturas según el tipo de documento (factura o nota de crédito)

**Tabla de contenidos**
=======================

.. contents::
   :local:

Configuración
=============

Este módulo se instala automáticamente cuando están presentes sus dependencias:

* ``account_payment_pro``: Módulo base para pagos avanzados
* ``l10n_ar_edi_ux``: Localización argentina para facturación electrónica

Uso
===

Wizard de Pago con Facturación
------------------------------

Cuando creas un pago con facturación automática, el wizard ahora incluye:

1. **Período de Asociación ARCA**:

   * Fecha de inicio del período
   * Fecha de fin del período

2. **Factura de Origen**:

   * Campo para seleccionar la factura original (útil para notas de crédito/débito)
   * Filtrado automático según el tipo de documento

Generación Automática de Períodos
---------------------------------

Para notas de débito generadas automáticamente por recargos financieros:

* El módulo detecta cuando se está creando una nota de débito automática
* Verifica si el diario es electrónico (ARCA)
* Configura automáticamente:

  * **Fecha Desde**: Fecha actual menos 1 mes
  * **Fecha Hasta**: Fecha actual

Filtrado de Facturas
--------------------

El sistema aplica filtros inteligentes en la selección de facturas de origen:

* **Para Notas de Crédito**: Solo facturas de cliente (``out_invoice``) en estado validado
* **Para Facturas Normales**: Facturas y notas de crédito de cliente en estado validado
* **Filtrado por Partner**: Solo facturas del mismo partner comercial

Créditos
========

Autores
~~~~~~~

* ADHOC SA

Contribuidores
~~~~~~~~~~~~~~

* ADHOC SA <info@adhoc.com.ar>

Mantenedores
~~~~~~~~~~~~

Este módulo es mantenido por ADHOC SA.

.. image:: https://www.adhoc.com.ar/logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

ADHOC SA es una empresa argentina especializada en desarrollo de soluciones Odoo.
