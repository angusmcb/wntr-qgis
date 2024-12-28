=================
PyQgis API
=================

This is the fledgling documentation for the work-in-progress API.

Please do not rely on this API. It is likely to change at every release.

Eventually, this API will allow you to use features in PyQGIS scripts and within the python console in QGIS.

Usage
======

A simple usage in the qgis console is as follows:

>>> layers = wq.to_qgis(wq.examples.KY10)
>>>
>>> # make edits to layers in qgis then...
>>>
>>> wn = wq.from_qgis(layers)


Note that when using outside of the console it is necessary to import ``wntrqgis`` and ``wntr`` as follows:

>>> import wntrqgis as wq
>>> import wntr


Reference
=========

.. automodule:: wntrqgis
	:members:
