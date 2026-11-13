.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-LGPL--3-blue.png
   :target: https://www.gnu.org/licenses/lgpl
   :alt: License: LGPL-3

=======================
ARBA Webservice (A122R)
=======================

Este módulo implementa:

* Webservice para conectar con ARBA al webservice A122R que permite para retenciones de ingresos brutos:

   * Inciar una declaración jurada, vincular una ya abierta en ARBA y actualizar su estado (también con una acción planificada diaria)
   * Crear un Comprobante de retención para cada retención de ARBA de un pago a proveedor, al validar el pago (modo automático) o con el botón "ARBA" de la línea de retención
   * Avisar, al volver a borrador un pago, que tiene retenciones ya informadas a ARBA

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

* En 'Contabilidad / Configuración / Ajustes' en sección "Localización para Argentina" sector ARBA van a poder

   * Configurar el ambiente a conectarse a ARBA (produccion, test, demo)
   * Configurar contraseña para conectar al webservice
   * Configurar el client ID y Client Secret
   * Elegir el modo de informe de retenciones: automático al validar el pago, o importación por lotes

DEV:
   * Seguimos la especificación del webservice A122R de ARBA disponible en el documento "Interfaz ServiciosA122RApiExternos.pdf" provisto por ARBA.
   * Para pruebas en desarrollo se puede ir a la colección Postman "A122RServices (ARBA WS)" disponible con el usuario de Soporte Adhoc.

Usage
=====

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: http://runbot.adhoc.com.ar/

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
