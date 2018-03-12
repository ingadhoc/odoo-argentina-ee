# -*- coding: utf-8 -*-
##############################################################################
#
#    Copyright (C) 2015  ADHOC SA  (http://www.adhoc.com.ar)
#    All Rights Reserved.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
{
    'name': 'Web Support Issue - Server',
    'version': '9.0.1.3.0',
    'category': 'Support',
    'sequence': 14,
    'summary': '',
    'description': """
Web Support Issue - Server
==========================
Gives possibility to web support clients to load issues
    """,
    'author': 'ADHOC SA',
    'website': 'www.adhoc.com.ar',
    'license': 'AGPL-3',
    'images': [
    ],
    'depends': [
        'web_support_server',
        # modulo requerido por algunos campos adicionales en los issues
        'infrastructure_contract',
        # modulo requerido para que web support client pueda cargar incidencias
        'project_issue',
    ],
    'data': [
        'views/database_user_view.xml',
        'views/project_issue.xml',
        'views/project_view.xml',
        'data/message_data.xml',
    ],
    'demo': [
    ],
    'test': [
    ],
    'installable': False,
    'auto_install': True,
    'application': False,
}
