Creating and Editing the Model
==============================

The model can consist of up to six layers:

- three node layers: junctions, reservoirs and tanks
- three link layers: pipes, valve, and pumps

Each of the six objects is reperesented in QGIS by it's own layer. Layers do not need to be created if they are not used for the model. There is a convenience function to create these empty layers with appropriate fields and some default styling, but any layer with the appropriate geometry type (points for nodes and linestrings for links) and with the minimum necessary fields can be used.

Creating Layers
---------------

You can use the 'new' button on the toolbar to create a set of layers with default properites.

.. image:: ../_static/new_button.png

Alternatively, for more control, you can use the 'Create Template Layers' processing tool.

You can also use any existing layers.


Attributes
-----------
Attributes are based on the attributes within WNTR, with some adaptations:

* All layers can optionally use the attribute 'name' to give a name to each item, which will be visible on the output layer. This must be a string. If no name is given, it will be automatically generated.
* All patterns and curves are input to each element, rather than as a reference to a pattern within WNTR.
* All geographical (coordinates, vertices) and netowrk-related (start_node_name and end_node_name) attributes are calculated automatically based on the geomtry of the features.

All attributes are optional, except those marked *Required*

.. table:: Possible Junction Layer Attributes

    +---------------------+------------------------------+
    | Attribute           | If not set                   |
    +=====================+==============================+
    | base_demand         | *Required*                   |
    +---------------------+------------------------------+
    | elevation           | 0                            |
    +---------------------+------------------------------+
    | demand_pattern      | No pattern - constant demand |
    +---------------------+------------------------------+
    | emitter_coefficient | None                         |
    +---------------------+------------------------------+
    | initial_quality     | 0                            |
    +---------------------+------------------------------+

.. table:: Possible Reservoir Layer Attributes

    +---------------------+------------------------------+
    | Attribute           | If not set                   |
    +=====================+==============================+
    | base_head           | 0                            |
    +---------------------+------------------------------+
    | head_pattern        | No pattern - constant head   |
    +---------------------+------------------------------+
    | initial_quality     | 0                            |
    +---------------------+------------------------------+

.. table:: Possible Tank Layer Attributes

    +---------------------+------------------------------+
    | Attribute           | If not set                   |
    +=====================+==============================+
    | elevation           | 0                            |
    +---------------------+------------------------------+
    | init_level          | *Required*                   |
    +---------------------+------------------------------+
    | min_level           | 0                            |
    +---------------------+------------------------------+
    | max_level           | *Required*                   |
    +---------------------+------------------------------+
    | diameter            | *Required*                   |
    +---------------------+------------------------------+
    | min_vol             | 0                            |
    +---------------------+------------------------------+
    | vol_curve           | No curve- cylindrical tank   |
    +---------------------+------------------------------+
    | overflow            | False                        |
    +---------------------+------------------------------+
    | inital_quality      | 0                            |
    +---------------------+------------------------------+
    | mixing_fraction     | None                         |
    +---------------------+------------------------------+
    | mixing_model        | None                         |
    +---------------------+------------------------------+
    | bulk_coeff          | None                         |
    +---------------------+------------------------------+

.. table:: Possible Pipe Layer Attributes

    +---------------------+------------------------------+
    | Attribute           | If not set                   |
    +=====================+==============================+
    | diameter            |                              |
    +---------------------+------------------------------+
    | roughness           |                              |
    +---------------------+------------------------------+
    | minor_loss          |                              |
    +---------------------+------------------------------+
    | initial_status      |                              |
    +---------------------+------------------------------+
    | check_valve         |                              |
    +---------------------+------------------------------+
    | bulk_coeff          |                              |
    +---------------------+------------------------------+
    | wall_coeff          |                              |
    +---------------------+------------------------------+

Optional:
* Elevation (default: 0)
*
