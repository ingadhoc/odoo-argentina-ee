.. |company| replace:: ADHOC SA

.. |company_logo| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-logo.png
   :alt: ADHOC SA
   :target: https://www.adhoc.com.ar

.. |icon| image:: https://raw.githubusercontent.com/ingadhoc/maintainer-tools/master/resources/adhoc-icon.png

.. image:: https://img.shields.io/badge/license-AGPL--3-blue.png
   :target: https://www.gnu.org/licenses/agpl
   :alt: License: AGPL-3

===================
Helpdesk Project UX
===================

This module ensures that:

* You can configure a project to have or not related tickets, by default they
  are not related to tickets.

* In project kanban view we are able to see the project related tickets
  analogous to tasks work, also have a Ticket Analysis submenu that let us
  to analyze the ticket data from a pivot or graph view.

* You can only close a ticket if they don't have any active task (we consider
  active task the ones in stages without option "folded")

* You can only close projects if they don't have any active ticket (we
  consider active tickets the ones in stages without option "folded")

* For the tickets, only can relate to project which are allowed tickets.

* When we set a helpdesk team to trace timesheet then the related project of
  the team will be set to be ticket allowed even if the project is a new
  project or we are linking an old one.

* When you (un)archive a project with also (un)archive

Installation
============

To install this module, you need to:

#. Only install this module

Configuration
=============

To configure this module, you need to:

#. Noting to configure

Usage
=====

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: http://runbot.adhoc.com.ar/

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/ingadhoc/project/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed feedback.

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
