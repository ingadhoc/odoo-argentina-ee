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

TODO: implementar sicore para percepciones, por ahora solo esta para retenciones (y de ganancias)
Especificación de archivos:

* SICORE: Algunoas links de neteres:

 * Detalle con captura de lo que solicita y lo que tenemos implementado: http://www.planillasutiles.com.ar/2014/09/hoja-de-calculos-para-importar-las.html

* SIFERE: https://drive.google.com/open?id=0B3trzV0e2WzvcG5kOVI5cTdjQm1lSWtpcFhzVFlWSlctQ0Nv y mas data aca http://www.ca.gov.ar/faqs/preguntas-generales/sifere/sifere-faq/como-armar-los-archivos-en-formato-txt-para-cargar-los-conceptos-de-retenciones-percepciones-comunes-y-aduaneras-y-recaudaciones-bancarias-en-el-aplicativo-sifere. Mas de sifere tmb acá https://drive.google.com/open?id=0B3trzV0e2WzvUjB1MnhXT0VteFE

* SIFERE en xml web?: http://www.comarb.gov.ar/descargar/faqs/sifere_web/importacion_xml_sifereweb.pdf

* ARBA: https://www.arba.gov.ar/Apartados/Agentes/PresentacionDDJJ.asp?lugar=P?apartado=AGENTES

* AGIP: https://www.agip.gob.ar/filemanager/source/Agentes/DocTecnicoImpoOperacionesDise%C3%B1odeRegistro.pdf y https://www.agip.gob.ar/agentes/agentes-de-recaudacion/ib-agentes-recaudacion/aplicativo-arciba/ag-rec-arciba-codigo-de-normas

* MENDOZA https://www.atm.mendoza.gov.ar/portalatm/ModificarParametros?tipo=descargarUrl&url=/zoneBottom/serviciosDescargas/sarepe/files/SAREPE.pdf

* DREI retenciones aplicadas:
   Longitud total de 151 caracteres.
   ** Estructura del archivo:
   cuit (req): 11, razon_soc (req): 80, nro_certificado: 10, fecha_ret: 10 (formato "dd/mm/aaaa"), base_imp: 09.2, alicuota: 09.6, importe (req): 09.2
   Los campos "base_imp","alicuota","importe" son  numéricos , deben completarse con ceros a la izquierda y tienen "." decimal.

* MISIONES: https://www.atm.misiones.gob.ar/index.php/guia-de-tramites/instructivos/category/53-agentes
            Correo DGR: mesadeayuda@tsgroup.com.ar

Inflation Adjustment
--------------------

The index are extracted from https://www.facpce.org.ar/indices-facpce/ page

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
