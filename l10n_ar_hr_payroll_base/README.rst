=====================================
Argentina - Sueldos: módulo base
=====================================

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

Parte de Odoo de la liquidación de sueldos híbrida: los datos maestros del personal, el recibo, el asiento, los
pagos y el libro de sueldos digital (LSD). **Odoo no calcula ningún importe.** El cálculo (sueldo, aportes,
contribuciones, SAC, liquidación final y Ganancias) lo hace una skill de Tuqui, que lee los datos de Odoo y escribe
los importes en el recibo.

**Tabla de contenidos**

.. contents::
   :local:

Qué hay en Odoo
===============

* **Ficha del empleado** (pestaña **Libro de sueldos**): CUIL, legajo, fecha de antigüedad reconocida, códigos ARCA
  (condición, actividad, modalidad de contratación, siniestrado, zona y obra social), historial de situación de revista
  e historial de cónyuge e hijos a cargo.
* **Catálogo de códigos ARCA** del LSD (Nómina > Configuración > Códigos ARCA).
* **Situación de revista desde las entradas de trabajo:** cada tipo de entrada de trabajo puede llevar su situación de
  revista (vacaciones = 12, licencia sin goce = 13). Al calcular el recibo, cada día toma la del historial del
  empleado, salvo que tenga una entrada de trabajo con situación propia. El resultado queda en el recibo (pestaña
  **Libro de sueldos**) y se puede corregir antes de validar.
* **Tres estructuras** (mensual, SAC y liquidación final) con el catálogo de conceptos. Cada concepto es una regla que
  copia el importe de su entrada del recibo; solo ``GROSS`` y ``NET`` suman categorías.
* **Recibo** con el formato del art. 140 de la Ley 20.744 y el costo laboral, enviado por mail al validar el lote.
* **Un asiento por lote**, con la línea de sueldos a pagar abierta por empleado, y la acción **Registrar pagos a
  empleados** en el lote, que genera un pago por empleado.
* **Libro de sueldos digital:** acción en el lote que genera el TXT.

Contrato con la skill
=====================

Es lo que tiene que mantenerse estable entre versiones de Odoo para que la skill sirva a varias empresas.

**Lo que lee:** la ficha del empleado (los campos de arriba, el sueldo y las fechas de la versión del empleado), las
ausencias y entradas de trabajo del período y los recibos de meses anteriores (por ejemplo, para el SAC o para los
brutos de Ganancias).

**Dónde escribe**, en cada recibo en borrador:

#. Una **entrada** (``hr.payslip.input``) por concepto: el tipo de entrada tiene el código del concepto (``BASIC``,
   ``JUB``, ``GAN``, ``CJUB``...), el importe va **siempre positivo** y el signo lo pone la categoría (los descuentos
   restan). En ``GAN``, un importe negativo es una devolución. Opcionales: la descripción (reemplaza el nombre del
   concepto en el recibo), ``l10n_ar_quantity`` y ``l10n_ar_unit`` (días o porcentaje, para el recibo y el LSD).
   Varias entradas del mismo concepto dan varias líneas.
#. La **base imponible con tope** (``l10n_ar_contribution_base``), para el registro 04 del LSD.
#. Después, **Calcular hoja**: arma las líneas a partir de las entradas y recalcula la situación de revista.

Un concepto nuevo se agrega como tipo de entrada y regla con el mismo código en cada estructura, sin código Python.

Configuración
=============

#. **Contabilidad > Ajustes de nómina:** activar el asiento agrupado por lote.
#. **Cuentas de las reglas**, en cada estructura:

   * Conceptos remunerativos, no remunerativos e indemnizaciones: cuenta deudora de sueldos y jornales.
   * ``NET``: cuenta acreedora de sueldos a pagar, conciliable. La regla ya viene con
     "Asignar empleado en la línea contable".
   * Descuentos (``JUB``, ``LEY19032``, ``OS``, ``GAN``, ``DEDUCTION``, ``ATTACH_SALARY``): tienen importe negativo,
     así que van con **cuenta deudora** igual a cargas sociales a pagar u otro pasivo.
   * Contribuciones: cuenta deudora de cargas sociales (gasto) y cuenta acreedora de cargas sociales a pagar.

#. **Tipos de entrada de trabajo:** la situación de revista de los que la cambian (por ejemplo, licencias).
#. **Empleado:** los datos de la pestaña **Libro de sueldos**, con el historial de situación de revista (hasta tres
   cambios por mes) y el de cónyuge e hijos a cargo; la CBU en la cuenta bancaria del empleado.
#. **Lote:** fecha de pago y fecha de pago de aportes; las dos salen en el recibo.

Uso
===

Con datos demo, la instalación arma un caso completo: compañía **Distribuidora SRL - Sueldos** con plan contable RI,
diario **Sueldos y Jornales**, empleado **Colaborador Adhoc** con dos feriados y tres días de vacaciones en septiembre
de 2026, y el lote con los importes cargados como los carga la skill, validado, con su asiento publicado, el pago, el
mail con el recibo y el TXT del libro de sueldos adjunto al lote.

Pendiente: validar el TXT del libro de sueldos en el aplicativo de ARCA.

Fuera de alcance: el cálculo de cualquier importe, convenios colectivos y firma de recibos.

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
