Creating and Editing the Model
==============================

The model can consist of up to six layers:

- three node layers: junctions, reservoirs and tanks
- three link layers: pipes, valve, and pumps

Each of the six objects is represented in QGIS by it's own layer. Layers do not need to be created if they are not used for the model. There is a convenience function to create these empty layers with appropriate fields and some default styling, but any layer with the appropriate geometry type (points for nodes and linestrings for links) and with the minimum necessary fields can be used.

Creating Layers
---------------

You can use the 'new' button on the toolbar to create a set of layers with default properties.

.. image:: ../_static/new_button.png

Alternatively, for more control, you can use the 'Create Template Layers' processing tool.

It is also possible to use any layer - you do not have to use the layers created by the plugin.


Attributes
-----------
Attributes are based on the attributes within WNTR.

All attributes are optional, and unless otherwise stated will use WNTR default values if not defined.

**Name** All layers can optionally use the attribute `name` to give a name to each item, which will be visible on the output layer. This must be a string. If no name is given, it will be automatically generated.

**Patterns** All patterns are string fields. This can be left blank. Otherwise, it should be input as a series of numbers seperated by spaces:

``1  1.2 1.3 0.8``

Patterns will also accept a field of type list, where each item in the list is a number.

**Curves** Curves should be inputted with the following form, where each pair of numbers in brackets is an x, y point on the curve.

``(0, 10), (2, 5), (3.3, 7)``

**Geographical attributes** All geographical (`coordinates`, `vertices`) and network-related (`start_node_name` and `end_node_name`) WNTR attributes are not used. This is because they are calculated automatically based on the geometry of the features.





.. csv-table:: Possible Junction Attributes
    :file: autogen-includes/junctions.csv
    :header-rows: 1

.. csv-table:: Possible Reservoir Attributes
    :file: autogen-includes/reservoirs.csv
    :header-rows: 1

.. csv-table:: Possible Tank Attributes
    :file: autogen-includes/tanks.csv
    :header-rows: 1

.. csv-table:: Possible Pipes Attributes
    :file: autogen-includes/pipes.csv
    :header-rows: 1

.. csv-table:: Possible Pumps Attributes
    :file: autogen-includes/pumps.csv
    :header-rows: 1

.. csv-table:: Possible Valve Attributes
    :file: autogen-includes/valves.csv
    :header-rows: 1
