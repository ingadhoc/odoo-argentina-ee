Referencias Oficiales SIRCIP
============================

Documentos incluidos en esta carpeta
--------------------------------------

* ``Diseno_de_Registros_del_Sistema_SIRCIP.pdf``
  Especificación oficial del diseño de registros para el padrón y la DDJJ.
  Fuente: https://www.ca.gob.ar/descargas/sircip/registros/Diseno_de_Registros_del_Sistema_SIRCIP.pdf

Links externos (pueden actualizarse)
--------------------------------------

* **Portal SIRCIP (descarga de padrón y carga de DDJJ)**
  https://www.ca.gob.ar/sistemas/sircip

* **Provincias adheridas y su estado de implementación**
  https://docs.google.com/spreadsheets/d/1yqf8C6ztxJZsmEQRC4-g2RttgMoJCqMi-Y-0_1mlugE/edit?gid=0#gid=0

* **Matriz de Aplicación de Códigos — Campo 7 (pestaña "Aplicacion Códigos")**
  https://docs.google.com/spreadsheets/d/1MXUlg43Ng-xBIx7xO5epLf21qJCEX7oFWpCzZ2b8PIk/edit?gid=664128533#gid=664128533

* **Recopilación de Q&A CESSI sobre SIRCIP**
  https://docs.google.com/document/d/1Apl-WG06AZZHXB70uVAWbzcg3sw1ncshoaBVcTdw8AE/edit?tab=t.0

* **Flujo de implementación en Odoo (presentación)**
  https://docs.google.com/presentation/d/1ciYJWrTBlt4gbxkt2J-BnJ2j5TvtU7lB/edit?slide=id.g354e669c7ff_0_12

Notas sobre el diseño de registros
------------------------------------

Padrón (CSV, separado por comas):
  periodo, cuit, razon_social_contri, jurisdiccion_sede, crc, alicuota_unica_letra, campo7

DDJJ (CSV, separado por comas, 17 campos):
  cuit, crc, fecha, tipo_regimen, tipo_registro, cod_op_exceptuada, jurisdiccion,
  tipo_comprobante, letra, punto_venta, nro_comprobante, monto_base, alicuota,
  monto_percibido, nro_original, crc_devolucion, abm

Campo 7 (25 chars numéricos):
  - Se lee de DERECHA a IZQUIERDA
  - Posición 24 (rightmost, índice = len-1) es siempre '0' y se descarta
  - Posición de cada jurisdicción: índice = 924 - jurisdiction_code
    (ej: CABA=901 → índice 23; Tucumán=924 → índice 0)
  - Valores: 1=solo básica, 2=básica+sobretasa, 3=excluido, 4/5=básica+alícuota propia
