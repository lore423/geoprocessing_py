from qgis.core import QgsVectorLayer
import processing
from qgis.core import *
from PyQt5.QtCore import *
from qgis.PyQt.QtWidgets import QAbstractItemView

quarto = QgsProject.instance()
commune =  quarto.mapLayersByName('Communes')[0]
#selecctioner les couches des contraintes à la main de la liste 
selected_layers = iface.layerTreeView().selectedLayers()

#selecctionner la commune/dept/EPCI/Region à la main et obtenir l'emprise
def emprise(input):
    commune_bbox = processing.run("native:boundingboxes",
                 { 'INPUT' : QgsProcessingFeatureSourceDefinition (input.id(), True),
                'OUTPUT': "TEMPORARY_OUTPUT"}
                )["OUTPUT"]
                
    return quarto.addMapLayer(commune_bbox)

commune_emprise = emprise(commune)


#fonction clip des contraintes par rapport l'emprise
def clipping(input, overlay):
    layers_clip = processing.run('qgis:clip',
                {'INPUT': input,
                'OVERLAY': overlay,
                'OUTPUT': "TEMPORARY_OUTPUT"}
                )["OUTPUT"]

    return quarto.addMapLayer(layers_clip)

#fonction merge des contraintes
def merge (input):
    layers_merge = processing.run("native:mergevectorlayers", 
                {'LAYERS':input,
                'CRS':QgsCoordinateReferenceSystem('EPSG:2154'),
                'OUTPUT': "TEMPORARY_OUTPUT"}
                )["OUTPUT"]
                
    return quarto.addMapLayer(layers_merge)

#Executer la fonction clipping
layers_clip = []
for f in selected_layers:
    res = clipping(f, commune_emprise)
    layers_clip.append(res)

#executer la fonction merge
merge_layer = merge(layers_clip)

 
##difference entre le resultat du merge et l'emprise
def difference (input, overlay):
    layers_difference = processing.run("native:difference", 
                    { 'INPUT' : QgsProcessingFeatureSourceDefinition (input.id(), True),
                    'OVERLAY':overlay,
                    'OUTPUT': "TEMPORARY_OUTPUT"}
                    )["OUTPUT"]
                    
    return quarto.addMapLayer(layers_difference)

#executer la fonction difference
difference_layers = difference(commune, merge_layer)

#fonction de conversion des morceaux multiples à morceaux uniques
def multi_to_single (input):
    multi_single = processing.run("native:multiparttosingleparts", 
                {'INPUT': input,
                'OUTPUT': "TEMPORARY_OUTPUT"}
                )["OUTPUT"]
                
    return quarto.addMapLayer(multi_single)

#executer la fonction multi_to_single
multi_to_single(difference_layers)


for layer in iface.layerTreeView().selectedLayers():
    layer.setName('Zones potentielles brutes')
##distances aux postes sources


##filtrer en fonction de la surface des ZPB
#
