.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-LGPL--3-blue.png
   :target: https://www.gnu.org/licenses/lgpl
   :alt: License: LGPL-3

===========================================
SIRCIP — Percepciones Convenio Multilateral
===========================================

.. warning::

   **Módulo exclusivo para Agentes de Percepción del SIRCIP.**

   Este módulo es solo para empresas que actúan como **Agentes de Percepción del SIRCIP**
   (Sistema de Recaudación del Control sobre Ingresos Brutos de Convenio Multilateral).
   No debe instalarse en empresas que no sean agentes de percepción de este régimen.

SIRCIP es el mecanismo de **ARCA** (ex AFIP) para la recaudación de percepciones de Ingresos
Brutos bajo el régimen de **Convenio Multilateral**. Es el equivalente al SIPRIB para empresas CM.

Instalación
===========

#. Instalar el módulo ``l10n_ar_account_tax_settlement`` (dependencia obligatoria).
#. Instalar este módulo ``l10n_ar_sircip``.
#. El ``post_init_hook`` crea automáticamente por empresa:

   * Grupo de impuestos **SIRCIP**
   * Impuestos base: ``SIRCIP A 0.0``, ``SIRCIP Sobre Alícuota 1%``, ``SIRCIP No Inscripto 2%``
   * Posición fiscal **Percepción - SIRCIP** (auto-detectable, secuencia 9999)
   * Diario de liquidación **SIRCIP Aplicado**

Configuración
=============

Provincias adheridas
--------------------

El módulo marca automáticamente con ``l10n_ar_is_sircip = True`` las provincias de la
**Etapa 1 (01/07/2026)**:

* ✅ Chaco, Jujuy, Mendoza, Río Negro, Salta, San Juan, Santiago del Estero, Tierra del Fuego

Las provincias adheridas sin fecha de Etapa 1 confirmada están comentadas en
``data/res_country_state_data.xml``. Descomentar a medida que entren en vigencia.

**Fuente oficial de adhesiones:** `Spreadsheet de provincias SIRCIP <https://docs.google.com/spreadsheets/d/1yqf8C6ztxJZsmEQRC4-g2RttgMoJCqMi-Y-0_1mlugE/edit?gid=0#gid=0>`_

Impuestos y posición fiscal
---------------------------

La posición fiscal ``Percepción - SIRCIP`` usa ``webservice = "padron"`` y detecta
automáticamente que corresponde al SIRCIP porque el impuesto apunta a la provincia
ficticia ``SIRCIP`` (``state_ar_sircip``).

Para configurar el código de régimen de percepción en cada impuesto SIRCIP, ir a
``Contabilidad → Configuración → Impuestos`` y completar el campo **Código AFIP**
(``l10n_ar_code``) con el código de régimen que corresponde a cada jurisdicción.

Uso
===

Carga del Padrón
----------------

#. Ir a ``Contabilidad → Configuración → AFIP → Padrón de Alícuotas por Compañía``.
#. Crear un nuevo registro con:

   * **Jurisdicción:** ``SIRCIP`` (la provincia ficticia creada por el módulo)
   * **Desde / Hasta:** rango del período del padrón (ej. 01/02/2026 - 28/02/2026)
   * **Archivo:** subir el TXT descargado del `Portal Federal Tributario — Descargas <https://www.ca.gob.ar/>`_

**Formato del padrón (CSV separado por comas):**

.. code-block:: text

   periodo,cuit,razon_social_contri,jurisdiccion_sede,crc,alicuota_unica_letra,campo7
   202602,30100100106,MI EMPRESA SA,904,34,B,5225355222512555552512420

Tabla de alícuotas (letras A–X):

+-------+-------+-------+-------+-------+-------+
| A=0%  | E=0.2%| I=0.6%| M=1.2%| Q=1.8%| U=3.5%|
+-------+-------+-------+-------+-------+-------+
| B=0.01| F=0.3%| J=0.7%| N=1.4%| R=2%  | V=4%  |
+-------+-------+-------+-------+-------+-------+
| C=0.05| G=0.4%| K=0.8%| O=1.5%| S=2.5%| W=4.5%|
+-------+-------+-------+-------+-------+-------+
| D=0.1%| H=0.5%| L=1%  | P=1.6%| T=3%  | X=5%  |
+-------+-------+-------+-------+-------+-------+

Cálculo de percepciones en facturas
-------------------------------------

Cuando se crea una factura de venta para un cliente con domicilio de entrega en una
provincia adherida al SIRCIP, el sistema:

#. Aplica la posición fiscal ``Percepción - SIRCIP``.
#. Busca el padrón SIRCIP vigente para el período.
#. Lee la letra del cliente y determina la alícuota base.
#. Verifica el **Campo 7** para la provincia de entrega y determina si aplica:

   * Dígito 1: Solo tasa básica SIRCIP
   * Dígito 2: Tasa básica + sobrealícuota (1%)
   * Dígito 3: Excluido
   * Dígito 4/5: Tasa básica SIRCIP + alícuota propia de la provincia

#. Si el CUIT no está en el padrón, aplica ``SIRCIP No Inscripto 2%``.

La alícuota por cliente queda cacheada en la pestaña **Contabilidad** del contacto
(``l10n_ar.partner.tax``). El campo **Referencia** almacena el CRC y el Campo 7 para
trazabilidad: ``SIRCIP | crc:XX | campo7:YYYYY...``

Generación del TXT de DDJJ
---------------------------

#. Ir al diario **SIRCIP Aplicado**.
#. Abrir el período de liquidación deseado.
#. Usar la acción **Descargar TXT** para generar el archivo ``SIRCIP_DDJJ.txt``.
#. Importar en el menú *Declaración Jurada* del `Portal Federal Tributario — DDJJ <https://www.ca.gob.ar/sistemas/sircip>`_.

**Formato del TXT (CSV 17 campos):** ver ``doc/sircip/Diseno_de_Registros_del_Sistema_SIRCIP.pdf``

Referencias Oficiales
=====================

Los documentos de referencia se encuentran en la carpeta ``doc/sircip/``:

* `Diseño de Registros SIRCIP (PDF oficial) <https://www.ca.gob.ar/descargas/sircip/registros/Diseno_de_Registros_del_Sistema_SIRCIP.pdf>`_
* `Provincias adheridas al SIRCIP <https://docs.google.com/spreadsheets/d/1yqf8C6ztxJZsmEQRC4-g2RttgMoJCqMi-Y-0_1mlugE/edit?gid=0#gid=0>`_
* `Matriz de Aplicación de Códigos (Campo 7) <https://docs.google.com/spreadsheets/d/1MXUlg43Ng-xBIx7xO5epLf21qJCEX7oFWpCzZ2b8PIk/edit?gid=664128533#gid=664128533>`_
* `Recopilación Q&A CESSI <https://docs.google.com/document/d/1Apl-WG06AZZHXB70uVAWbzcg3sw1ncshoaBVcTdw8AE/edit?tab=t.0>`_
* `Portal Federal Tributario SIRCIP <https://www.ca.gob.ar/sistemas/sircip>`_

Pendientes
==========

Funcionalidad definida pero aún sin implementar
------------------------------------------------

**TXT de presentación de DDJJ — validación contra el sistema real**
  El método ``iibb_aplicado_sircip_files_values()`` genera el CSV de 17 campos
  según la especificación del PDF oficial. Pendiente validar contra el portal SIRCIP
  con archivos reales de un período completo y confirmar que las validaciones del
  sistema aceptan el formato generado.

**Dígito 3 del campo 7 — comportamiento bajo análisis de ARCA**
  El dígito 3 se define como "Excluido" en la especificación oficial pero su
  comportamiento exacto está pendiente de definición formal. Actualmente se trata
  igual que el dígito 1 (solo tasa básica SIRCIP). Ver resolución en el
  `Q&A CESSI <https://docs.google.com/document/d/1Apl-WG06AZZHXB70uVAWbzcg3sw1ncshoaBVcTdw8AE/edit?tab=t.0>`_
  y actualizar ``_get_sircip_extra_taxes()`` en
  ``models/account_fiscal_position_l10n_ar_tax.py``.

**Soporte de archivos comprimidos (ZIP/RAR) en la carga del padrón**
  Actualmente solo se acepta el archivo TXT plano. El padrón SIRCIP podría
  venir comprimido en futuras versiones del portal. Implementar en
  ``_get_sircip_aliquot()`` siguiendo el patrón existente de
  ``_read_parp_from_binary()`` para Santa Fe.

Configuración que el cliente debe realizar manualmente
------------------------------------------------------

**Posiciones fiscales provinciales para dígitos 4/5 del campo 7**
  Para contribuyentes donde el campo 7 indica dígito 4 o 5 (doble alícuota:
  SIRCIP + alícuota propia de la provincia), el sistema busca en orden:

  1. Un registro ``l10n_ar.partner.tax`` existente del contacto para esa provincia.
  2. Una posición fiscal con percepción configurada para esa jurisdicción.

  Si no encuentra ninguno, lanza un ``UserError`` explicativo. El cliente debe
  configurar las posiciones fiscales de las provincias que apliquen dígito 4/5.

**Código de régimen (l10n_ar_code) en los impuestos SIRCIP**
  Los impuestos SIRCIP creados por el módulo no tienen ``l10n_ar_code`` (Código AFIP)
  pre-configurado. El campo 4 del TXT DDJJ requiere este código. El cliente debe
  completarlo en ``Contabilidad → Configuración → Impuestos`` para cada impuesto
  SIRCIP antes de generar el TXT.

Datos que pueden cambiar antes de la fecha de inicio (01/07/2026)
------------------------------------------------------------------

**Provincias adheridas — Etapa 1**
  El archivo ``data/res_country_state_data.xml`` tiene activas 8 provincias de
  Etapa 1 y comentadas 10 provincias adheridas sin fecha confirmada. Antes del
  01/07/2026 verificar el
  `spreadsheet oficial de adhesiones <https://docs.google.com/spreadsheets/d/1yqf8C6ztxJZsmEQRC4-g2RttgMoJCqMi-Y-0_1mlugE/edit?gid=0#gid=0>`_
  y descomentar las que confirmen fecha de inicio.

  Provincias comentadas (adheridas, pendiente de etapa):
  CABA, Buenos Aires, Catamarca, Córdoba, Chubut, La Pampa, La Rioja, Misiones,
  Neuquén, Santa Cruz.

**Posiciones en el campo 7 por jurisdicción**
  El mapa ``SIRCIP_CAMPO7_POSITION`` en
  ``models/account_fiscal_position_l10n_ar_tax.py`` está construido a partir del
  PDF y ejemplos del padrón real. Si ARCA modifica el orden de las jurisdicciones
  en el campo 7 debe actualizarse.

Créditos
========

Imágenes
--------

* |company| |icon|

Autores
-------

* |company|

Maintainer
----------

|company_logo|
