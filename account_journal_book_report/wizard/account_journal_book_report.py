##############################################################################
# For copyright and license notices, see __manifest__.py file in root directory
##############################################################################
import base64

from dateutil.relativedelta import relativedelta
from markupsafe import Markup
from odoo import api, fields, models
from odoo.tools.misc import get_lang


class AccountJournalBookReport(models.TransientModel):
    _name = "account.journal.book.report"
    _inherit = "base.bg"
    _description = "Journal Book Report"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)

    journal_ids = fields.Many2many(
        comodel_name="account.journal",
        relation="account_journal_book_journal_rel",
        column1="acc_journal_entries_id",
        column2="journal_id",
        required=True,
        default=lambda self: self.env["account.journal"].search([("company_id", "=", self.company_id.id)]),
        domain="[('company_id', '=', company_id)]",
    )
    last_entry_number = fields.Integer(
        string="Último nº de asiento",
        required=True,
        default=0,
    )
    date_from = fields.Date(
        string="Start Date",
        required=True,
    )
    date_to = fields.Date(
        string="End Date",
        required=True,
    )

    target_move = fields.Selection(
        [
            ("posted", "All Posted Entries"),
            ("all", "All Entries"),
        ],
        string="Target Moves",
        required=True,
        default="posted",
    )

    @api.onchange("company_id")
    def _onchange_company_id(self):
        if dates := self.company_id.compute_fiscalyear_dates(fields.Date.from_string(fields.Date.today())):
            self.date_from = dates["date_from"]
            self.date_to = dates["date_to"]

    def _print_report(self, data):
        date_from = fields.Date.from_string(self.date_from)
        date_to = fields.Date.from_string(self.date_to)
        periods = []
        # por mas que el usuario pida fecha distinta al 1 del mes, los move
        # lines ya van a estar filtrados por esa fecha y por simplicidad
        # construimos periodos desde el 1
        dt_from = date_from.replace(day=1)
        while dt_from < date_to:
            dt_to = dt_from + relativedelta(months=1, days=-1)
            periods.append((fields.Date.to_string(dt_from), fields.Date.to_string(dt_to)))
            # este va a se la date from del proximo
            dt_from = dt_to + relativedelta(days=1)
        return (
            self.env["ir.actions.report"]
            .search([("report_name", "=", "account_journal_book_report")], limit=1)
            .with_context(
                periods=periods,
                last_entry_number=self.last_entry_number,
            )
            .report_action(self)
        )

    def _retrive_moves_ids(self):
        """Este método se llama desde el archivo account_journal_book_report.ods y sirve para obtener los asientos
        contables que estarán en el reporte de libro diario."""
        domain = [("company_id", "=", self.company_id.id)]
        if self.target_move == "posted":
            domain.append(("state", "=", "posted"))
        if self.date_from:
            domain.append(("date", ">=", self.date_from))
        if self.date_to:
            domain.append(("date", "<=", self.date_to))
        moves = self.env["account.move"].search(domain)
        return moves.ids

    def _build_contexts(self, data):
        result = {}
        result["journal_ids"] = "journal_ids" in data["form"] and data["form"]["journal_ids"] or False
        result["state"] = "target_move" in data["form"] and data["form"]["target_move"] or ""
        result["date_from"] = data["form"]["date_from"] or False
        result["date_to"] = data["form"]["date_to"] or False
        result["strict_range"] = True if result["date_from"] else False
        result["company_id"] = data["form"]["company_id"][0] or False
        return result

    def action_check_report(self):
        """Este método se llama desde el botón 'Imprimir' del wizard 'Libro Diario'"""
        self.ensure_one()
        if not self._context.get("bg_job"):
            return self.bg_enqueue("action_check_report")
        else:
            data = {}
            data["ids"] = self.env.context.get("active_ids", [])
            data["model"] = self.env.context.get("active_model", "ir.ui.menu")
            data["form"] = self.read(["date_from", "date_to", "journal_ids", "target_move", "company_id"])[0]
            used_context = self._build_contexts(data)
            data["form"]["used_context"] = dict(used_context, lang=get_lang(self.env).code)
            res = self.with_context(discard_logo_check=True)._print_report(data)
            reportname = res.get("report_name")
            report = self.env["ir.actions.report"].search([("report_name", "=", reportname)], limit=1)
            docids = res.get("context")["active_ids"]
            periods = res.get("context")["periods"]
            document, doc_format = report.with_context(
                must_skip_send_to_printer=True, last_entry_number=self.last_entry_number, periods=periods
            )._render_aeroo(reportname, docids, data=data)
            attachment = self.env["ir.attachment"].create(
                {
                    "name": reportname + ".xls",
                    "datas": base64.b64encode(document),
                    "res_model": self._name,
                    "type": "binary",
                    "company_id": self.company_id.id,
                }
            )

            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            download_url = f"{base_url}/web/content/{attachment.id}?download=true"

            res_html = f"""
                The following document has been generated:<br>
                <a href="{download_url}" target="_blank">{attachment.name}</a>
            """
            return Markup(res_html)
