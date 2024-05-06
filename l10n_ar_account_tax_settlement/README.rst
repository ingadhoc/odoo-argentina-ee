.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

=============================
Tax Settlements For Argentina
=============================

Este módulo imlementa:

* archivos para declaración de distintos impuestos (principalmente percepciones y retenciones)
* Funcionalidad y datos para auste por inflación (The index are extracted from https://www.facpce.org.ar/indices-facpce/)
* Al momento de instalar el módulo se agregan los códigos de impuestos correspondientes para retenciones de ganancias aplicadas y retenciones de iva aplicadas. También se agregan al momento de instalar el módulo las etiquetas de en las repartition lines de impuestos para percepciones. Lo descripto en este punto sucede en compañías argentinas responsable inscripto con plan de cuentas ri establecido.
* Se agregan códigos de impuestos a impuestos de retenciones de ganancias aplicadas y retenciones de iva aplicadas. Y también se agregan las etiquetas de en las repartition lines de impuestos para percepciones. Lo descripto en este punto se agrega en compañías responsable inscripto argentinas nuevas al momento de instalar plan de cuentas responsable inscripto.

Archivos para declaración de impuestos
======================================

TODO: implementar sicore para percepciones, por ahora solo esta para retenciones (y de ganancias)
Especificación de archivos:

* SICORE: Algunoas links de neteres:

 * Detalle con captura de lo que solicita y lo que tenemos implementado: http://www.planillasutiles.com.ar/2014/09/hoja-de-calculos-para-importar-las.html

* SIFERE: https://drive.google.com/open?id=0B3trzV0e2WzvcG5kOVI5cTdjQm1lSWtpcFhzVFlWSlctQ0Nv y mas data aca http://www.ca.gov.ar/faqs/preguntas-generales/sifere/sifere-faq/como-armar-los-archivos-en-formato-txt-para-cargar-los-conceptos-de-retenciones-percepciones-comunes-y-aduaneras-y-recaudaciones-bancarias-en-el-aplicativo-sifere. Mas de sifere tmb acá https://drive.google.com/open?id=0B3trzV0e2WzvUjB1MnhXT0VteFE

* SIFERE en xml web?: http://www.comarb.gov.ar/descargar/faqs/sifere_web/importacion_xml_sifereweb.pdf

* ARBA: https://www.arba.gov.ar/Apartados/Agentes/PresentacionDDJJ.asp?lugar=P?apartado=AGENTES

* AGIP:  https://www.agip.gob.ar/agentes/agentes-de-recaudacion/ib-agentes-recaudacion/aplicativo-arciba/aclaraciones-sobre-las-adecuaciones-al-aplicativo-e-arciba- (Version 3.0 aplicada el 07-05-2024)
   * Notas de credito  https://www.agip.gob.ar/filemanager/source/Agentes/De%20Recaudacion/Ingresos%20brutos/NC.PDF
   * Retencion y percepciones  https://www.agip.gob.ar/filemanager/source/Agentes/De%20Recaudacion/Ingresos%20brutos/RP.PDF

* MENDOZA https://www.atm.mendoza.gov.ar/portalatm/ModificarParametros?tipo=descargarUrl&url=/zoneBottom/serviciosDescargas/sarepe/files/SAREPE.pdf

* DREI retenciones aplicadas:
   Longitud total de 151 caracteres.
   ** Estructura del archivo:
   cuit (req): 11, razon_soc (req): 80, nro_certificado: 10, fecha_ret: 10 (formato "dd/mm/aaaa"), base_imp: 09.2, alicuota: 09.6, importe (req): 09.2
   Los campos "base_imp","alicuota","importe" son  numéricos , deben completarse con ceros a la izquierda y tienen "." decimal.

* Retenciones y percepciones de IVA sufridas:
   * Especificación en ticket 54274 (en una archivo adjunto IVAEspecificación Percepcion y Retencinoes Iva.pdf)

* MISIONES: https://www.atm.misiones.gob.ar/index.php/guia-de-tramites/instructivos/category/53-agentes
            Correo DGR: mesadeayuda@tsgroup.com.ar


Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

#. Nothing to configure

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
