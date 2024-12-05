import datetime
from unittest.mock import patch


import odoo.tests.common as common
from odoo.exceptions import UserError


class TestUpdateFromAfip(common.TransactionCase):

    def testmonotributo(self):
        """Actualizamos un contacto del tipo monotributo"""

        # Chequeamos que no hay actividades ni impuestos creados
        self.assertEqual(self.env['afip.activity'], self.env['afip.activity'].search([]), "Activities are not being created.")
        self.assertEqual(self.env['afip.tax'], self.env['afip.tax'].search([]), "Taxes are not being created.")

        contacto = self.env['res.partner'].create({
            'name': 'Partner Monotributo',
            'vat': '20221064233',
            'l10n_latam_identification_type_id': self.env.ref('l10n_ar.it_cuit').id,
        })

        mocked_res = {
            'name': 'MARJORIER, LAMARA', 'estado_padron': 'ACTIVO', 'street': 'LARREA 1 Piso:2 Dpto:2 S:4 T:1 M:6', 'city': None,
            'zip': '1030', 'actividades_padron': [2], 'impuestos_padron': [2], 'imp_iva_padron': 'NI', 'monotributo_padron': 'S',
            'actividad_monotributo_padron': 'A VENTAS DE COSAS MUEBLES', 'empleador_padron': False, 'integrante_soc_padron': '',
            'last_update_padron': datetime.date(2024, 9, 27), 'imp_ganancias_padron': 'NC', 'state_id': 553,
            'l10n_ar_afip_responsibility_type_id': 6}

        mocked_res_1 = {
            'expiration_time': datetime.datetime(2024, 9, 28, 2, 43, 28),
            'generation_time': datetime.datetime(2024, 9, 27, 14, 43, 28),
            'sign': 'owXfXllz1533lHmrOIW81BVZoVzku5LU90aM7WvjeZGh78CXEw4RcFDEMTrK1s3uROX3hWlZ9o0+zectr2jYGBOcvlEQJn2uZ9ler4RT+s/9/DIBfGfDYm+xGIeerOyPrBiG/R48JWw1xdLqpPFSyYoVK8Y1oULvEZomF8WSm74=',
            'token': 'PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiIHN0YW5kYWxvbmU9InllcyI/Pgo8c3NvIHZlcnNpb249IjIuMCI+CiAgICA8aWQgc3JjPSJDTj13c2FhaG9tbywgTz1BRklQLCBDPUFSLCBTRVJJQUxOVU1CRVI9Q1VJVCAzMzY5MzQ1MDIzOSIgdW5pcXVlX2lkPSIxMDAwMTU0NTIwIiBnZW5fdGltZT0iMTcyNzQ0ODE0OCIgZXhwX3RpbWU9IjE3Mjc0OTE0MDgiLz4KICAgIDxvcGVyYXRpb24gdHlwZT0ibG9naW4iIHZhbHVlPSJncmFudGVkIj4KICAgICAgICA8bG9naW4gZW50aXR5PSIzMzY5MzQ1MDIzOSIgc2VydmljZT0id3Nfc3JfY29uc3RhbmNpYV9pbnNjcmlwY2lvbiIgdWlkPSJTRVJJQUxOVU1CRVI9Q1VJVCAyMDMxMzkzMjk3NSwgQ049b2Rvb2NlcnQyIiBhdXRobWV0aG9kPSJjbXMiIHJlZ21ldGhvZD0iMjIiPgogICAgICAgICAgICA8cmVsYXRpb25zPgogICAgICAgICAgICAgICAgPHJlbGF0aW9uIGtleT0iMjAyMjIyMjIyMjMiIHJlbHR5cGU9IjQiLz4KICAgICAgICAgICAgICAgIDxyZWxhdGlvbiBrZXk9IjMwMTExMTExMTE4IiByZWx0eXBlPSI0Ii8+CiAgICAgICAgICAgICAgICA8cmVsYXRpb24ga2V5PSIzMDcxNDEwMTQ0MyIgcmVsdHlwZT0iNCIvPgogICAgICAgICAgICAgICAgPHJlbGF0aW9uIGtleT0iMzA5OTk5OTk5OTUiIHJlbHR5cGU9IjQiLz4KICAgICAgICAgICAgPC9yZWxhdGlvbnM+CiAgICAgICAgPC9sb2dpbj4KICAgIDwvb3BlcmF0aW9uPgo8L3Nzbz4K',
            'uniqueid': '1727448208'
        }

        with patch("odoo.addons.l10n_ar_edi_ux.models.res_partner.ResPartner.get_data_from_padron_afip", return_value=mocked_res), \
             patch("odoo.addons.l10n_ar_edi.models.l10n_ar_afipws_connection.L10nArAfipwsConnection._l10n_ar_get_token_data", return_value=mocked_res_1):
            res_id = contacto.button_update_partner_data_from_afip()['res_id']

        wiz = self.env['res.partner.update.from.padron.wizard'].browse(res_id)
        wiz.update_selection()

        self.assertEqual(contacto.name, 'Marjorier, Lamara', "Name after the update from afip must change")

        # Chequeamos que las actividades e impuestos se hayan creado con la actualizacion
        self.assertTrue(contacto.actividad_monotributo_padron, "Actividad monotributo padron are not being created.")
        self.assertTrue(contacto.actividades_padron, "Activities are not being created.")
        self.assertTrue(contacto.impuestos_padron, "Taxes are not being created.")

    def testresponsableinscripto(self):
        """Actualizamos un contacto del tipo Responsable Inscripto"""

        # Chequeamos que no hay actividades ni impuestos creados
        self.assertEqual(self.env['afip.activity'], self.env['afip.activity'].search([]), "Activities are not being created.")
        self.assertEqual(self.env['afip.tax'], self.env['afip.tax'].search([]), "Taxes are not being created.")

        contacto = self.env['res.partner'].create({
            'name': 'Partner Responsable Inscripto',
            'vat': '20188027963',
            'l10n_latam_identification_type_id': self.env.ref('l10n_ar.it_cuit').id,
        })
        res_id = contacto.button_update_partner_data_from_afip()['res_id']
        wiz = self.env['res.partner.update.from.padron.wizard'].browse(res_id)
        wiz.update_selection()

        self.assertEqual(contacto.name, 'Paniagua Koler, Venancio', "Name after the update from afip must change")

        # Chequeamos que las actividades e impuestos se hayan creado con la actualizacion
        self.assertTrue(contacto.actividades_padron, "Activities are not being created.")
        self.assertTrue(contacto.impuestos_padron, "Taxes are not being created.")

    def testcontactoerror(self):
        """Aseguramos de catchear bien el error del contacto"""

        contacto = self.env['res.partner'].create({
            'name': 'Partner Error',
            'vat': '30999999995',
            'l10n_latam_identification_type_id': self.env.ref('l10n_ar.it_cuit').id,
        })
        error_message = 'El número de documento informado es inválido'
        with self.assertRaisesRegex(UserError, error_message):
            contacto.button_update_partner_data_from_afip()
        self.assertTrue(error_message not in contacto.message_ids.mapped('body'), "Not message should be posted in the contact if there was an error")
