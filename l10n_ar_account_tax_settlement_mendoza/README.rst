.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

======================
Tax settlement Mendoza
======================

Este módulo imlementa:

* Cálculo de impuestos para retenciones de mendoza.

Installation
============

To install this module, you need to:

#. Only need to install the module

Configuration
=============

To configure this module, you need to:

* En 'Contabilidad / Configuración / Ajustes' en sección "Localización para Argentina" el usuario debe subir todas las semanas el archivo csv de riesgo fiscal en la sección de riesgo fiscal. Lo debe hacer para cada una de las compañías.
* El impuesto 'Retención IIBB Mendoza Aplicada' debe tener  código de regimen en el campo 'Codigo de regimen IVA' en solapa 'Opciones avanzadas' y debe calcularse con código python "\n# withholdable_base_amount\n# payment: account.payment.group object\n# partner: res.partner object (commercial partner of payment group)\n# withholding_tax: account.tax.withholding object\n\nmove_to_pay = payment.to_pay_move_line_ids.move_id\nactivities = move_to_pay.activities_mendoza_ids\nif activities:\n    activity_codes = activities.mapped('code')\n    partner_vat = move_to_pay.partner_id.l10n_ar_formatted_vat\n    actividades_con_riesgo, actividades_con_alicuota_cero = payment.company_id.process_mendoza_csv_file(partner_vat, activity_codes)\n    menor_alicuota = activities.menor_alicuota(actividades_con_alicuota_cero)\n\n    if menor_alicuota[0] in actividades_con_riesgo:\n           alicuota = menor_alicuota[1] * 2\n    else:\n           alicuota = menor_alicuota[1]\n    payment.write({'alicuota_mendoza': alicuota})\n    result = withholdable_base_amount * alicuota\nelse:\n    result = False\n        ". No hace falta establecer la configuración de código python en compañías existentes antes de instalar este módulo pero si es necesario hacerlo para compañías nuevas.
* Importar archivo actividades afip en 'Contabilidad / Configuracioń / AFIP / Actividades'.

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
