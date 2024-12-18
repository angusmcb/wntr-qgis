=================
API Introduction
=================

This is the fledgling documentation for the work-in-progress API.

Please do not rely on this API. It is likely to change at every release.

Eventually, this API will allow you to use features in PyQGIS scripts and within the python console in QGIS.

It can be imported within the QGIS environment as follow.

>>> from wntrqgis import interface, elements
>>>
>>> # wntr will be automatically added to the path by wntrqgis
>>> import wntr


>>> import wntrqgis
>>> wntrqgis.write_layers(wn, results=None,  crs=None, units=None, layers=None, fields:list = None,   filename=) -> dict[str, Layer]
>>> wntrqgis.write_geopackage(wn, filename,  results=None, units=LPS, layers=None, fields:list = None) -> layer
>>> wntrqgis.write_layer(wn, 'JUNCTIONS',  results=None, units=LPS, fields:list = None) -> layer


>>> wntrqgis.to_wntr(layers: dict['str', 'layer']  | geopackage, units='LPS', wn=None, project=None, crs=None)-> wn


>>> wntrqgis.Writer(wn,  results=None, units=None)
		.field_list =list[]
		.get_qgsfields(layer) = QgsFields
		.write(layer, sink)



>>> wntrqgis.ExampleInp.KY10
>>> wntrqgis.ExampleInp.SIMPLE
>>> wntrqgis.ExampleInp.ALLELEMENTS

>>> wntrqgis.ExampleLayers.KY10
>>> wntrqgis.ExampleLayers.ALLELEMENTS
