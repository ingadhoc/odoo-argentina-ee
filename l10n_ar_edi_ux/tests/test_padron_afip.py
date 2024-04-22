from odoo import fields
from odoo.tests import common

class PadronAfipTest(common.TransactionCase):

    def test_check_padron_afip(self):
        response_responsable_inscripto = {
            'datosGenerales': {
                'apellido': None,
                'caracterizacion': [],
                'dependencia': None,
                'domicilioFiscal': {
                    'codPostal': '6500',
                    'datoAdicional': None,
                    'descripcionProvincia': 'BUENOS AIRES',
                    'direccion': 'PERICO 772',
                    'idProvincia': 1,
                    'localidad': 'FAUZON',
                    'tipoDatoAdicional': None,
                    'tipoDomicilio': 'FISCAL'
                },
                'esSucesion': 'NO',
                'estadoClave': 'ACTIVO',
                'fechaFallecimiento': None,
                'idPersona': 30111111118,
                'mesCierre': 12,
                'nombre': None,
                'razonSocial': "GRANGY 'S S.A.",
                'tipoClave': 'CUIT',
                'tipoPersona': 'JURIDICA'
            },
            'datosMonotributo': None,
            'datosRegimenGeneral': {
                'actividad': [
                    {
                        'descripcionActividad': 'FABRICACIÓN DE CARTELES, SEÑALES E INDICADORES  -ELÉCTRICOS O NO-',
                        'idActividad': 329030,
                        'nomenclador': 883,
                        'orden': 1,
                        'periodo': 201311
                    }
                ],
                'categoriaAutonomo': None,
                'impuesto': [
                    {'descripcionImpuesto': 'GANANCIAS SOCIEDADES', 'idImpuesto': 10, 'periodo': 201801},
                    {'descripcionImpuesto': 'IVA', 'idImpuesto': 30, 'periodo': 199202},
                    {'descripcionImpuesto': 'REGIMENES DE INFORMACIÓN', 'idImpuesto': 103, 'periodo': 201112},
                    {'descripcionImpuesto': 'BP-ACCIONES O PARTICIPACIONES', 'idImpuesto': 211, 'periodo': 202212},
                    {'descripcionImpuesto': 'SICORE-IMPTO.A LAS GANANCIAS', 'idImpuesto': 217, 'periodo': 199603},
                    {'descripcionImpuesto': 'IMPUESTO REMESA DE UTILIDADES', 'idImpuesto': 271, 'periodo': 201001},
                    {'descripcionImpuesto': 'SCA ART 96 INC A, D Y/O E.', 'idImpuesto': 314, 'periodo': 201301},
                    {'descripcionImpuesto': 'CONTRIBUCIONES SEG. SOCIAL', 'idImpuesto': 351, 'periodo': 200501},
                    {'descripcionImpuesto': 'RETENCIONES CONTRIB.SEG.SOCIAL', 'idImpuesto': 353, 'periodo': 200001},
                    {'descripcionImpuesto': 'ADICIONAL EMERG.CIGARRILLOS', 'idImpuesto': 366, 'periodo': 201909},
                    {'descripcionImpuesto': 'INTERNOS-OBJETOS SUNTUARIOS', 'idImpuesto': 481, 'periodo': 200903},
                    {'descripcionImpuesto': 'SICORE - RETENCIONES Y PERCEPC', 'idImpuesto': 767, 'periodo': 199603},
                    {'descripcionImpuesto': 'IIBB CONVENIO MULTILATERAL', 'idImpuesto': 5900, 'periodo': 201911}
                ],
                'regimen': [
                    {'descripcionRegimen': 'COMPRA/VENTA GRANOS Y LEGUMBRES SEC. ART10 INC.A).2- OP. PRIMARIAS', 'idImpuesto': 217, 'idRegimen': 22, 'periodo': 199603, 'tipoRegimen': 'RETENCION'},
                    {'descripcionRegimen': 'SUBSIDIOS ABONADOS POR ESTADOS NACIONAL...', 'idImpuesto': 217, 'idRegimen': 780, 'periodo': 200807, 'tipoRegimen': 'RETENCION'},
                    {'descripcionRegimen': 'EMPRESAS DE SERVICIOS EVENTUALES', 'idImpuesto': 353, 'idRegimen': 742, 'periodo': 200001, 'tipoRegimen': 'RETENCION'},
                    {'descripcionRegimen': 'REG.PER.AL VALOR AGREGADO - EMPRESAS...', 'idImpuesto': 767, 'idRegimen': 493, 'periodo': 200001, 'tipoRegimen': 'PERCEPCION'},
                    {'descripcionRegimen': None, 'idImpuesto': 767, 'idRegimen': 786, 'periodo': 199603, 'tipoRegimen': None},
                    {'descripcionRegimen': 'RANCHO - DISTRIBUIDORES', 'idImpuesto': 103, 'idRegimen': 73, 'periodo': 20200102, 'tipoRegimen': None}
                ]
            },
            'errorConstancia': None,
            'errorMonotributo': None,
            'errorRegimenGeneral': None,
            'metadata': {
                'servidor': 'setiwsh2'
            }
        }
        partner = self.env['res.partner']
        res = partner._clean_response_obj(response_responsable_inscripto, default_replace={})
        for key, value in res.items():
            if isinstance(value, dict):
                for key, value in res.items():
                    self.assertNotEqual(None, value, "El response que evaluaste tiene datos None")
            if isinstance(value, list):
                for val in value:
                    for key, value in val.items():
                        self.assertNotEqual(None, value, "El response que evaluaste tiene datos None")
            else:
                self.assertNotEqual(None, value, "El response que evaluaste tiene datos None")
