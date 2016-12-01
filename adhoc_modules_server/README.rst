.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

====================
ADHOC Modules Server
====================

* Add repositories model, and import modules from them
* Manage your modules database
* Link modules categories to product
* Add contract type on products
* Add wizard to generate cotract lines

Installation
============

To install this module, you need to:

#. Do this ...

Configuration
=============

To configure this module, you need to:

#. Add a github token on parameters

Usage
=====

To use this module, you need to:

#. Go to ...

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: https://runbot.adhoc.com.ar/

.. repo_id is available in https://github.com/OCA/maintainer-tools/blob/master/tools/repos_with_ids.txt
.. branch is "8.0" for example

Known issues / Roadmap
======================

#### Pendientes:

* Links documentación a modulos
* Llevar documentación a clientes
* Agregar linea en rojo si cantidad teorica distinta de real. Agregar un booleano en la vista lista tmb (el tema es los productos que no se leen, los computamos con 1?)
* ver de agregar reglas de incompatibilidad entre modulos (ver como hace odoo en v9 de temas)
* ver modulos instalados y no categorizados
* Actualizar contratos con un boton, mostrar con un campo related el precio de lista actual (segun lista de precios del contrato)
* que contratar te cargue una incidencia con el proyecot que se quiere contratar
* TODO ver si las categorias invisibles es practico que sean visibles para admi
* Podriamos simplificar la integracion usando el modulo que permite importar no por id si no por otros campo, entonces usariamos "name" e id de categori
* Vincular documentos o temas a un módulo para que luego de instalarlo al client lo lleve a la documentación correspondient
* Si el auto refresh con wizard desde kanban no nos gusta, podemos ver esto https://github.com/szufisher/web/tree/8.0/web_auto_refres
* Agregar campo calculado en modulos de adhoc "also available for", que busque otro modulo con mismo nombre. También que deje, con un boton, copiar data de los otros modulos (mezclando todos los datos que existan), que dicha acción se pueda correr tambien desde la vist lista de modulos
* al cancelar una instalación de un modulo, mostrar los módulos que van a dejar de ser instalados también porque requerian a este (parecido a lo que hacemos al instalar
* Agregar version requerida en los modulos o algo por el estilo para que se actualice automáticamente (vamos a ver si en realidad lo manejamos de otra manera lo de actualizar a todo el mundo)

    
####Pendientes low priority:

* Evaluar si es mejor entrar a la kanban de categorías con un default_group_by="parent_id" para que permita drag and drop y de un solo vistazo vez todas las categorías, tipo dashboard.
* implementar suggested subcategories
* Sacar warning de "InsecurePlatformWarning: A true SSLContext object is not available."


Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/{project_repo}/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed feedback.

Credits
=======

Images
------

* ADHOC SA: `Icon <http://fotos.subefotos.com/83fed853c1e15a8023b86b2b22d6145bo.png>`_.

Contributors
------------


Maintainer
----------

.. image:: http://fotos.subefotos.com/83fed853c1e15a8023b86b2b22d6145bo.png
   :alt: Odoo Community Association
   :target: https://www.adhoc.com.ar

This module is maintained by the ADHOC SA.

To contribute to this module, please visit https://www.adhoc.com.ar.
