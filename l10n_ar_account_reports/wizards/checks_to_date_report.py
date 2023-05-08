##############################################################################
# For copyright and license notices, see __manifest__.py file in module root
# directory
##############################################################################
from odoo import models, fields, api


class AccountCheckToDateReportWizard(models.TransientModel):
    _name = 'account.check.to_date.report.wizard'
    _description = 'account.check.to_date.report.wizard'

    journal_id = fields.Many2one(
        'account.journal',
        string='Diario',
        domain=[
            '|',
            ('outbound_payment_method_line_ids.code', '=', 'check_printing'),
            ('inbound_payment_method_line_ids.code', '=', 'in_third_party_checks'),
            ],
    )
    to_date = fields.Date(
        'Hasta Fecha',
        required=True,
        default=fields.Date.today,
    )

    def action_confirm(self):
        self.ensure_one()
        force_domain = self.journal_id and [('journal_id', '=', self.journal_id.id)] or []
        return self.env.ref('l10n_ar_account_reports.checks_to_date_report').report_action(self)

    @api.model
    def _get_checks_handed(self, journal_id, to_date):
        '''
        hacemos una query que:
        * toma todos los pagos correspondientes a un cheque
        * dentro de esos pagos filtramos por los que no tengan matched_debit_ids
        * dentro de account.full.reconcile buscar todas las que tengas asocido un pago que corresponda a un cheque, una vez filtrado,
        * obtener la otra linea de ese full reconcile ya que esta corresponde a la conciliacion hecha en el date determinado
        * entonces lo que filtramos finalmente sera, los cheques aun no fueron debitados y sean de fecha anterior a la dada o los que tiene debito luego de la fecha dada

        -> en account.full.reconcile:
        reconciled_line_ids.filtered(lambda x: x.move_id.payment_id.payment_method_id.code == 'check_printing').payment_id.ids -> nos da los id de los pagos correspondientes a un cheque que fueron conciliados
        -> esto nos da en la fecha en la cual fueron debitados:
        self.env['account.full.reconcile'].search([]).reconciled_line_ids.filtered(lambda x: x.move_id.payment_id.payment_method_id.code == 'check_printing')
        .full_reconcile_id.reconciled_line_ids.filtered(lambda x: x.statement_line_id).mapped(lambda x: x.date)
        '''
        to_date = str(to_date)
        query = """
                SELECT DISTINCT ON (t.check_id) t.check_id AS cheque FROM
                    (
                        SELECT ap.id as check_id, ap_move.date as operation_date, apm.code as operation_code
                        FROM account_payment ap
                        LEFT JOIN account_payment_method AS apm ON apm.id = ap.payment_method_id
                        LEFT JOIN account_move AS ap_move ON ap.move_id = ap_move.id
                        LEFT JOIN account_journal AS journal ON ap_move.journal_id = journal.id
                        WHERE
                        apm.code = 'check_printing' AND ap_move.date <= '%s' order by ap.id, ap_move.date desc, ap.id desc
                    ) t
                    LEFT JOIN
                    (
                        SELECT ap.id as check_id, afr_full.name as conciliation_name, aml_2.date as operation_date, aml.id as aml_1, aml_2.id as aml_2
                        FROM account_payment ap
                        JOIN account_payment_method AS apm ON apm.id = ap.payment_method_id
                        JOIN account_move_line as aml ON ap.move_id = aml.move_id
                        JOIN account_full_reconcile AS afr_full ON afr_full.id = aml.full_reconcile_id
                        JOIN account_move_line AS aml_2 ON aml_2.full_reconcile_id = afr_full.id
                        WHERE apm.code = 'check_printing' AND aml.id <> aml_2.id
                    ) t2
                    ON t.check_id = t2.check_id
                WHERE t2.operation_date >= '%s' OR t2.operation_date IS NULL
                ;
                """ % (to_date, to_date)
        self.env.cr.execute(query)
        res = self.env.cr.fetchall()
        check_ids = [x[0] for x in res]
        checks = self.env['account.payment'].search([('id', 'in', check_ids)])
        if journal_id:
            checks = self.env['account.payment'].search([('id', 'in', check_ids),('journal_id','=', journal_id)])
        return checks

    @api.model
    def _get_checks_on_hand(self, journal_id, to_date):
        """
        Hacemos una query que:
        * toma todos los pagos que representan un cheque hasta cierta fecha en una tabla t
        * arma todas las operaciones de cheques hasta cierta fecha
        * de esa tabla obtenemos la ultima operación anterior a la fecha que queremos analizar
        * si esa ultima operación NO es enviar cheque, lo consideramos en mano
        * a esta query le unimos otra query que tome los casos de delivered third check (a traves de las tablas t3/t4)
        """
        to_date = str(to_date)
        query = """
        SELECT * FROM (
            SELECT DISTINCT ON (t.check_id) t.check_id AS cheque
            FROM
                (
                    SELECT ap.id as check_id, ap_move.date as operation_date, apm.code as operation_code
                    FROM account_payment ap
                    LEFT JOIN account_payment_method AS apm ON apm.id = ap.payment_method_id
                    LEFT JOIN account_move AS ap_move ON ap.move_id = ap_move.id
                    LEFT JOIN account_journal AS journal ON ap_move.journal_id = journal.id
                    WHERE
                    apm.code = 'new_third_party_checks' AND ap_move.date <= '%s' AND ap.l10n_latam_check_current_journal_id IS NOT NULL
                ) t
                LEFT JOIN
                (
                    SELECT DISTINCT ON (ap_check_op.l10n_latam_check_id) ap_check_op.l10n_latam_check_id as check_id, ap_check_op.id as payment_id, ap_check_op_move.date as operation_date, apm.code as operation_code, pair_apm.code as paired_code, ap_check_op.l10n_latam_check_current_journal_id as journal
                    FROM account_payment ap_check_op
                    LEFT JOIN account_move AS ap_check_op_move ON ap_check_op.move_id = ap_check_op_move.id
                    LEFT JOIN account_payment_method AS apm ON apm.id = ap_check_op.payment_method_id
                    LEFT JOIN account_payment AS pair_ap ON pair_ap.id = ap_check_op.paired_internal_transfer_payment_id
                    LEFT JOIN account_payment_method as pair_apm ON pair_apm.id = pair_ap.payment_method_id
                    WHERE
                    ap_check_op.l10n_latam_check_id IS NOT NULL AND ap_check_op_move.date <= '%s'
                    ORDER BY check_id, operation_date desc, payment_id desc
                ) t2
                ON t.check_id = t2.check_id
            WHERE t2.operation_date IS NULL OR (t2.operation_code != 'out_third_party_checks' AND paired_code != 'out_third_party_checks')
            UNION ALL
            SELECT DISTINCT ON (t4.check_id) t4.check_id as cheque
            FROM
                (
                    SELECT ap.l10n_latam_check_id as check_id
                    FROM account_payment ap
                    LEFT JOIN account_payment_method AS apm ON apm.id = ap.payment_method_id
                    LEFT JOIN account_move AS ap_move ON ap.move_id = ap_move.id
                    LEFT JOIN account_journal AS journal ON ap_move.journal_id = journal.id
                    WHERE
                    apm.code = 'out_third_party_checks' AND ap_move.date > '%s'
                    AND
                    ap.l10n_latam_check_current_journal_id IS NULL
                ) t3
                JOIN
                (
                    SELECT ap.id as check_id, ap.l10n_latam_check_current_journal_id as journal
                    FROM account_payment ap
                    LEFT JOIN account_payment_method AS apm ON apm.id = ap.payment_method_id
                    LEFT JOIN account_move AS ap_move ON ap.move_id = ap_move.id
                    LEFT JOIN account_journal AS journal ON ap_move.journal_id = journal.id
                    WHERE
                    apm.code = 'new_third_party_checks' AND ap_move.date <= '%s'
                ) t4
                ON t3.check_id = t4.check_id
            WHERE t4.journal IS NULL
            ) general
            ORDER BY general.cheque
            ;
        """ % (to_date, to_date, to_date, to_date)
        self.env.cr.execute(query)
        res = self.env.cr.fetchall()
        check_ids = [x[0] for x in res]
        checks = self.env['account.payment'].search([('id', 'in', check_ids)])
        if journal_id:
            checks = self.env['account.payment'].search([('id', 'in', check_ids),('journal_id','=',journal_id)])
        return checks
