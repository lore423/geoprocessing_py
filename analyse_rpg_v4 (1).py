from qgis.core import QgsProcessing
from qgis.core import QgsProcessingAlgorithm
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterRasterLayer
from qgis.core import QgsProcessingParameterField
from qgis.core import QgsProcessingParameterDistance
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterFeatureSink
from qgis.core import QgsProcessingParameterExpression
import processing


class Analyse_rpg_v4(QgsProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterVectorLayer('rpgentree', 'Couche RPG', types=[QgsProcessing.TypeVectorPolygon], defaultValue=None))
        self.addParameter(QgsProcessingParameterExpression('codegroup', 'Filtrer en fonction du code du group et la surface des parcelles', parentLayerParameterName='rpgentree', defaultValue='\"CODE_GROUP\"=\'17\' AND $area/10000  > 10'))
        self.addParameter(QgsProcessingParameterVectorLayer('postessources', 'Couche des postes sources', types=[QgsProcessing.TypeVectorPoint], defaultValue=None))
        self.addParameter(QgsProcessingParameterDistance('distanceauxpostessoruces', 'Distance aux postes sources', parentParameterName='postessources', defaultValue=10000))
        self.addParameter(QgsProcessingParameterField('attributedelacouchepostesources', 'Id de la couche postes sources pour déterminer la distance aux parcelles RPG', type=QgsProcessingParameterField.Any, parentLayerParameterName='postessources', allowMultiple=False, defaultValue='ogc_fid'))
        self.addParameter(QgsProcessingParameterField('idjointure', 'id jointure', type=QgsProcessingParameterField.Any, parentLayerParameterName='postessources', allowMultiple=False, defaultValue='ogc_fid'))
        self.addParameter(QgsProcessingParameterRasterLayer('Pente', 'Couche de Pente', defaultValue=None))
        self.addParameter(QgsProcessingParameterExpression('pentemoyenne', 'Valeur de la pente', parentLayerParameterName='', defaultValue='\"pente_mean\" <15'))
        self.addParameter(QgsProcessingParameterFeatureSink('ParcellesSelectionnes', 'Parcelles selectionnées', optional=True, type=QgsProcessing.TypeVectorAnyGeometry, createByDefault=True, defaultValue=None))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(8, model_feedback)
        results = {}
        outputs = {}

        # Extraire rpg par expression
        alg_params = {
            'EXPRESSION': parameters['codegroup'],
            'INPUT': parameters['rpgentree'],
            'FAIL_OUTPUT': QgsProcessing.TEMPORARY_OUTPUT,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtraireRpgParExpression'] = processing.run('native:extractbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Tampon
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': parameters['distanceauxpostessoruces'],
            'END_CAP_STYLE': 0,
            'INPUT': parameters['postessources'],
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Tampon'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Découper un raster selon une emprise
        alg_params = {
            'DATA_TYPE': 0,
            'EXTRA': '',
            'INPUT': parameters['Pente'],
            'NODATA': None,
            'OPTIONS': '',
            'PROJWIN': outputs['ExtraireRpgParExpression']['FAIL_OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DcouperUnRasterSelonUneEmprise'] = processing.run('gdal:cliprasterbyextent', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Extraire rpg from tampon postes sources
        alg_params = {
            'INPUT': outputs['ExtraireRpgParExpression']['OUTPUT'],
            'INTERSECT': outputs['Tampon']['OUTPUT'],
            'PREDICATE': [0],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtraireRpgFromTamponPostesSources'] = processing.run('native:extractbylocation', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}


        # Statistiques de zone
        alg_params = {
            'COLUMN_PREFIX': 'pente_',
            'INPUT_RASTER': outputs['DcouperUnRasterSelonUneEmprise']['OUTPUT'],
            'INPUT_VECTOR': outputs['ExtraireRpgFromTamponPostesSources']['OUTPUT'],
            'RASTER_BAND': 1,
            'STATS': [2]
        }
        outputs['StatistiquesDeZone'] = processing.run('qgis:zonalstatistics', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}
            
        # Extraire parcelles par expression (pente moyenne)
        alg_params = {
            'EXPRESSION': parameters['pentemoyenne'],
            'INPUT': outputs['ExtraireRpgFromTamponPostesSources']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtraireParcellesParExpressionPenteMoyenne'] = processing.run('native:extractbyexpression', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}


        # Distance au plus proche hub (ligne vers hub)
        alg_params = {
            'FIELD': parameters['attributedelacouchepostesources'],
            'HUBS': parameters['postessources'],
            'INPUT': outputs['ExtraireParcellesParExpressionPenteMoyenne']['OUTPUT'],
            'UNIT': 0,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DistanceAuPlusProcheHubLigneVersHub'] = processing.run('qgis:distancetonearesthublinetohub', alg_params, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # Joindre les attributs par valeur de champ
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'FIELD': 'ogc_fid',
            'FIELDS_TO_COPY': 'HubDist',
            'FIELD_2': parameters['idjointure'],
            'INPUT': outputs['ExtraireParcellesParExpressionPenteMoyenne']['OUTPUT'],
            'INPUT_2': outputs['DistanceAuPlusProcheHubLigneVersHub']['OUTPUT'],
            'METHOD': 1,
            'PREFIX': 'distance_',
            'OUTPUT': parameters['ParcellesSelectionnes']
        }
        outputs['JoindreLesAttributsParValeurDeChamp'] = processing.run('native:joinattributestable', alg_params, context=context, feedback=feedback, is_child_algorithm=True)
        results['ParcellesSelectionnes'] = outputs['JoindreLesAttributsParValeurDeChamp']['OUTPUT']
        return results

    def name(self):
        return 'Analyse_rpg_v4'

    def displayName(self):
        return 'Analyse_rpg_v4'

    def group(self):
        return 'Quarto'

    def groupId(self):
        return 'Quarto'

    def createInstance(self):
        return Analyse_rpg_v4()
