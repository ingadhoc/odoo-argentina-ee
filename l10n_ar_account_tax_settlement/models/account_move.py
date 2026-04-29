<<<<<<< HEAD
||||||| MERGE BASE
=======
##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
import csv
from io import StringIO

from odoo import _, models
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    def _get_document_number_parts(self):
        """Wrapper around _l10n_ar_get_document_number_parts for single-record use.
        Callers should invoke _validate_document_number_parts() on the full recordset
        first so that all invalid documents are reported at once."""
        self.ensure_one()
        return self._l10n_ar_get_document_number_parts(
            self.l10n_latam_document_number, self.l10n_latam_document_type_id.code
        )

    def _validate_document_number_parts(self):
        """Validate document number format for all records in self.
        Collects every invalid document and raises a single ValidationError
        listing them all, instead of stopping at the first failure."""
        invalid = []
        for move in self:
            try:
                move._l10n_ar_get_document_number_parts(
                    move.l10n_latam_document_number, move.l10n_latam_document_type_id.code
                )
            except (ValueError, AttributeError):
                invalid.append(move)
        if invalid:
            doc_list = "\n".join(
                '- "%s" (id: %d): "%s"' % (m.display_name, m.id, m.l10n_latam_document_number) for m in invalid
            )
            raise ValidationError(
                _(
                    "The following document(s) have an invalid document number format.\n"
                    "ARCA requires the format XXXXX-XXXXXXXX (e.g.: 00001-00000001).\n"
                    "Please correct them before generating the file:\n%s"
                )
                % doc_list
            )

    def action_download_vat_differences_csv(self):
        """Acción para descargar CSV con diferencias de IVA"""
        try:
            handler = self.env["l10n_ar.tax.report.handler"]
            vat_differences_data = handler._check_invoices(self)

            if not vat_differences_data:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Información"),
                        "message": _("No se encontraron diferencias de IVA para las facturas seleccionadas."),
                        "type": "info",
                    },
                }

            # Generar el contenido del CSV
            csv_content = self._generate_vat_differences_csv(vat_differences_data)
            filename = "Diferencias_iva.csv"

            # Usar el download_files_wizard para mostrar el archivo
            files_values = [
                {
                    "txt_filename": filename,
                    "txt_content": csv_content,
                }
            ]

            return self.env["res.download_files_wizard"].action_get_files(files_values)

        except Exception as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Error"),
                    "message": _("Error al generar el CSV: %s") % str(e),
                    "type": "danger",
                },
            }

    def _generate_vat_differences_csv(self, vat_differences_data):
        """Genera el contenido del CSV con las diferencias de IVA"""
        output = StringIO()
        writer = csv.writer(output, delimiter=",", quotechar='"', quoting=csv.QUOTE_MINIMAL)
        header = [
            "Fecha",
            "Factura ID",
            "Contacto",
            "Factura Nombre",
            "Alícuota IVA",
            "Base Imponible",
            "Importe Reportado",
            "Importe Calculado",
            "Diferencia",
        ]
        writer.writerow(header)

        for row in vat_differences_data:
            if isinstance(row, (list, tuple)):
                csv_row = []
                for item in row:
                    if isinstance(item, tuple):  # For the case of (BaseImp, Importe)
                        csv_row.extend([str(x) for x in item])
                    else:
                        csv_row.append(str(item))
                writer.writerow(csv_row)
        if not vat_differences_data:
            return output.getvalue()

        # Assume all rows are of the same namedtuple type as the first row
        RowType = type(vat_differences_data[0])
        for row in vat_differences_data:
            if not isinstance(row, RowType):
                raise ValueError("Unexpected row type in vat_differences_data: %s" % type(row))
            csv_row = [
                str(getattr(row, "fecha", "")),
                str(getattr(row, "factura_id", "")),
                str(getattr(row, "contacto", "")),
                str(getattr(row, "factura_nombre", "")),
                str(getattr(row, "alicuota_iva", "")),
                str(getattr(row, "base_imponible", "")),
                str(getattr(row, "importe_reportado", "")),
                str(getattr(row, "importe_calculado", "")),
                str(getattr(row, "diferencia", "")),
            ]
            writer.writerow(csv_row)

        content = output.getvalue()
        output.close()
        return content

>>>>>>> FORWARD PORTED
