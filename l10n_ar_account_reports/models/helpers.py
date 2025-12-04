import re
import unicodedata

from odoo.tools import ustr

#########
# helpers
#########


def format_amount(amount, padding=15, decimals=2, sep=""):
    if amount < 0:
        template = "-{:0>%dd}" % (padding - 1 - len(sep))
    else:
        template = "{:0>%dd}" % (padding - len(sep))
    res = template.format(int(round(abs(amount) * 10**decimals, decimals)))
    if sep:
        res = f"{res[:-decimals]}{sep}{res[-decimals:]}"
    return res


def get_line_tax_base(move_line):
    return sum(move_line.move_id.line_ids.filtered(lambda x: move_line.tax_line_id in x.tax_ids).mapped("balance"))


def get_pos_and_number(full_number):
    """
    Para un numero nos fijamos si hay '-', si hay:
    * mas de 1, entonces devolvemos error
    * 1, entonces devolvemos las partes (solo parte númerica)
    * 0, entonces devolvemos '0' y parte númerica del número que se pasó
    """
    args = full_number.split("-")
    if len(args) == 1:
        # si no hay '-' tomamos punto de venta 0
        return ("0", re.sub("[^0-9]", "", args[0]))
    else:
        return re.sub("[^0-9]", "", args[0]), re.sub("[^0-9]", "", "".join(args[1:]))


def remove_accents_and_dieresis(input_str):
    """Suboptimal-but-better-than-nothing way to replace accented or dieresis-containing
    latin letters by an ASCII equivalent."""
    input_str = ustr(input_str)
    nkfd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nkfd_form if not unicodedata.combining(c)])


def get_standard_lines_domain(company_ids, options):
    domain = [("company_id", "in", company_ids)]
    state = options.get("all_entries") and "all" or "posted"
    if state and state.lower() != "all":
        domain += [("move_id.state", "=", state)]
    if options.get("date").get("date_to"):
        domain += [("date", "<=", options["date"]["date_to"])]
    if options.get("date").get("date_from"):
        domain += [("date", ">=", options["date"]["date_from"])]
    return domain
