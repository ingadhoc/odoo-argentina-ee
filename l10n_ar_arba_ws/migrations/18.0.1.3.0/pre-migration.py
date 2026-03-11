import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Para los clientes que ya crearon retenciones, quedo el en name la mezcla
    de "numero de cert ARBA + numero interno"

    Queremos que:
    1. en el name quede solo numero cert ARBA
    2. que el numero interno se guarde en el campo ref"""
    _logger.info("Fixing wh line name: Separating ARBA cert number and internal number in name and ref fields")
    cr.execute(r"""
        UPDATE l10n_ar_payment_withholding
        SET
            ref = substring(name from '\(([^()]*)\)$'),
            name = l10n_ar_cert_number
        WHERE l10n_ar_cert_number IS NOT NULL
        AND l10n_ar_cert_number <> ''
        AND (ref IS NULL OR ref = '')
        AND name ~ '^[^()]+ \([^()]+\)$';
    """)
