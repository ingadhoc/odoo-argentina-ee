# Part of Odoo. See LICENSE file for full copyright and licensing details.

import io
from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    def create_document_from_attachment(self, attachment_ids=None):
        # OVERRIDE
        journal = self or self.browse(self.env.context.get('default_journal_id'))

        if journal.type == 'purchase' and journal.company_id.country_code == 'AR':
            attachments = self.env['ir.attachment'].browse(attachment_ids or [])

            if not attachments:
                raise UserError(_("No attachment was provided"))
            return journal.import_bills_from_xls(attachments)
        return super().create_document_from_attachment(attachment_ids)

    def import_bills_from_xls(self, attachments):

        # company = self.company_id

        for attachment in attachments:
            import pdb; pdb.set_trace()

            
            # fields = [
            #     "code",
            #     "name",
            #     "amount",
            #     "reference",
            #     "currency",
            #     "amount_company_currency",
            # ]

            # errors = list()  # For storing possible errors
            # move_lines = list()  # For storing items before generating 'em

            # Parseamos el archivo (UNICAMENTE CSV)
            # Sacamos el primer registro ya que este tiene el nombre de las columnas (TODO no ignorarlo para evitar errores)

            lines = io.BytesIO(attachment.raw).readlines()[1:]
            for line in lines:
                #En cada linea tenemos un registro de la factura
                print(line)
