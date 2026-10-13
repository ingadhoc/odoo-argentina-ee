======================================================
Argentina - Liquidación de sueldos (fuera de convenio)
======================================================

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

Liquidación de sueldos LCT fuera de convenio sobre la nómina de Odoo 19 Enterprise.

**Funcionalidades principales**
-------------------------------

* Tres estructuras: **LCT: Mensual**, **LCT: SAC** y **LCT: Liquidación final**.
* Conceptos: sueldo básico (30 días menos feriados y ausencias sin goce, a sueldo / 30), feriados (sueldo / 25),
  plus vacacional (días de vacaciones por la diferencia entre sueldo / 25 y sueldo / 30), otros remunerativos,
  no remunerativo, aportes (jubilación, ley 19.032 y obra social, con tope), deducción manual, embargo,
  contribuciones patronales, ART y seguro de vida.
* Liquidación final: SAC proporcional, vacaciones no gozadas, preaviso, integración del mes de despido e
  indemnización por antigüedad, cada una con su SAC cuando corresponde.
* Datos del libro de sueldos digital en el empleado (pestaña **Libro de sueldos**) y el generador del archivo TXT
  (acción **Libro de sueldos digital** en el lote).
* Recibo con el formato del art. 140 de la Ley 20.744, enviado por mail con el PDF adjunto al validar el lote.
* Un solo asiento por lote, con la línea de sueldos a pagar abierta por empleado, y la acción
  **Registrar pagos a empleados** en el lote, que genera un pago por empleado.

**Tabla de contenidos**
=======================

.. contents::
   :local:

Configuración
=============

#. **Contabilidad > Ajustes de nómina:** activar el asiento agrupado por lote.
#. **Cuentas de las reglas**, en cada estructura:

   * Conceptos remunerativos, no remunerativos e indemnizaciones: cuenta deudora de sueldos y jornales.
   * ``NET``: cuenta acreedora de sueldos a pagar, conciliable. La regla ya viene con
     "Asignar empleado en la línea contable".
   * Aportes (``JUB``, ``LEY19032``, ``OS``), ``DEDUCTION`` y ``ATTACH_SALARY``: tienen importe negativo, así que
     van con **cuenta deudora** igual a cargas sociales a pagar u otro pasivo.
   * Contribuciones: cuenta deudora de cargas sociales (gasto) y cuenta acreedora de cargas sociales a pagar.

#. **Feriados:** en los feriados del calendario, poner el tipo de entrada de trabajo **Feriado** (``LEAVE500``).
#. **Parámetros** (Nómina > Configuración > Parámetros de reglas): el tope de aportes, la ART fija y el seguro de
   vida cambian seguido; hay que cargar el valor nuevo con su fecha de vigencia.
#. **Empleado:** CUIL, legajo y códigos ARCA en la pestaña **Libro de sueldos**, con el historial de situación de
   revista (hasta tres cambios por mes) y el de cónyuge e hijos a cargo, cada línea con su fecha de inicio; la CBU en la
   cuenta bancaria del empleado.
#. **Lote:** fecha de pago y fecha de pago de aportes; las dos salen en el recibo.

Uso
===

En junio y diciembre se liquida primero el mensual y después el SAC: el SAC toma la mejor remuneración mensual del
semestre entre los recibos ya generados.

Con datos demo, la instalación arma un caso completo: compañía **Distribuidora SRL - Sueldos** con plan contable RI, diario
**Sueldos y Jornales**, empleado **Colaborador Adhoc** (sueldo $1.000.000), dos feriados y tres días de vacaciones en
septiembre de 2026, una deducción "Internet" de $10.000, el lote validado con su asiento publicado, el pago, el mail
con el recibo y el TXT del libro de sueldos adjunto al lote.

Fuera de alcance: convenios colectivos, impuesto a las ganancias (SIRADIG, F.1359, SICORE), sueldo por hora y firma
de recibos.

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
