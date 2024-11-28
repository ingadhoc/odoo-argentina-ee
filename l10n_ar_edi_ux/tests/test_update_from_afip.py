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

        contacto =  self.env['res.partner'].create({
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
