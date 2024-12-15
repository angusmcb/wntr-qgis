
================
Units
================

The plugin uses the same sets of units as Epanet, including both SI-based units and US customary units. Some units also depend on the equation used.
For reference, :numref:`table-epanet-units` includes unit conversions.


.. note::
    Within the WNTR python module all units are in pure SI. This plugin automatically translates units to and from SI when reading and writing QGIS Layers.






.. _table-epanet-units:
.. table:: EPANET INP File Unit Conventions

   +----------------------+-------------------------------------+------------------------------------+
   |   Parameter          |   US customary units                |   SI-based units                   |
   +======================+=====================================+====================================+
   | Concentration        |  *mass* /L where *mass* can be      |  *mass* /L where *mass* can be     |
   |                      |  defined as mg or ug                |  defined as mg or ug               |
   +----------------------+-------------------------------------+------------------------------------+
   | Demand               |   Same as *flow*                    |   Same as *flow*                   |
   +----------------------+-------------------------------------+------------------------------------+
   | Diameter (Pipes)     |   in                                |   mm                               |
   +----------------------+-------------------------------------+------------------------------------+
   | Diameter (Tanks)     |   ft                                |   m                                |
   +----------------------+-------------------------------------+------------------------------------+
   | Efficiency (Pumps)   |   percent                           | percent                            |
   +----------------------+-------------------------------------+------------------------------------+
   | Elevation            |   ft                                |   m                                |
   +----------------------+-------------------------------------+------------------------------------+
   | Emitter coefficient  |   *flow* / sqrt(psi)                |  *flow* / sqrt(m)                  |
   +----------------------+-------------------------------------+------------------------------------+
   | Energy               |   kW-hours                          | kW-hours                           |
   +----------------------+-------------------------------------+------------------------------------+
   | Flow                 | - CFS: ft :sup:`3` /s               | - LPS: L/s                         |
   |                      | - GPM: gal/min                      | - LPM: L/min                       |
   |                      | - MGD: million gal/day              | - MLD: million L/day               |
   |                      | - IMGD: million imperial gal/day    | - CMH: m :sup:`3` /hr              |
   |                      | - AFD: acre-feet/day                | - CMD: m :sup:`3` /day             |
   +----------------------+-------------------------------------+------------------------------------+
   | Friction factor      |  unitless                           |  unitless                          |
   +----------------------+-------------------------------------+------------------------------------+
   | Hydraulic head       |   ft                                |   m                                |
   +----------------------+-------------------------------------+------------------------------------+
   | Length               |   ft                                |   m                                |
   +----------------------+-------------------------------------+------------------------------------+
   | Minor loss           |  unitless                           |  unitless                          |
   | coefficient          |                                     |                                    |
   +----------------------+-------------------------------------+------------------------------------+
   | Power                |   horsepower                        |   kW                               |
   +----------------------+-------------------------------------+------------------------------------+
   | Pressure             |   psi                               |   m                                |
   +----------------------+-------------------------------------+------------------------------------+
   | Reaction             |   1/day (1st-order)                 |  1/day (1st-order)                 |
   | coefficient (Bulk)   |                                     |                                    |
   +----------------------+-------------------------------------+------------------------------------+
   | Reaction             | - *mass* /ft/day (0-order)          | - *mass* /m/day (0-order)          |
   | coefficient (Wall)   | - ft/day (1st-order)                | - m/day (1st-order)                |
   +----------------------+-------------------------------------+------------------------------------+
   | Roughness            | - 0.001 ft (Darcy-Weisbach)         | - mm (Darcy-Weisbach)              |
   | coefficient          | - unitless (otherwise)              | - unitless (otherwise)             |
   +----------------------+-------------------------------------+------------------------------------+
   | Source mass          |   *mass* /min                       | *mass* /min                        |
   | injection rate       |                                     |                                    |
   +----------------------+-------------------------------------+------------------------------------+
   | Velocity             |   ft/s                              |   m/s                              |
   +----------------------+-------------------------------------+------------------------------------+
   | Volume               |   ft :sup:`3`                       |   m :sup:`3`                       |
   +----------------------+-------------------------------------+------------------------------------+
   | Water age            |   hours                             | hours                              |
   +----------------------+-------------------------------------+------------------------------------+


WNTR works using pure SI units, and it is also possible to select 'SI' as a unit set. This will use the following units:

* Acceleration = :math:`\rm g` (:math:`\rm g \equiv 9.80665 m/s^2`)
* Concentration = :math:`\rm kg/m^3`
* Demand = :math:`\rm m^3/s`
* Diameter = :math:`\rm m`
* Elevation = :math:`\rm m`
* Energy = :math:`\rm J`
* Flow rate = :math:`\rm m^3/s`
* Head = :math:`\rm m`
* Headloss = :math:`\rm m`
* Length = :math:`\rm m`
* Mass = :math:`\rm kg`
* Mass injection = :math:`\rm kg/s`
* Power = :math:`\rm W`
* Pressure head = :math:`\rm m` (assumes a fluid density of 1000 :math:`\rm kg/m^3`)
* Time = :math:`\rm s`
* Velocity = :math:`\rm m/s`
* Volume = :math:`\rm m^3`
