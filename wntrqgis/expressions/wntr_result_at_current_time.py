import math

from qgis.core import qgsfunction


# qgis 3.28 errors if 'feature' and 'parent' are not included
@qgsfunction(group="Water Network Tools for Resilience")
def wntr_result_at_current_time(column, feature, parent, context):  # noqa ARG001
    """
    Gets an individual result for the specified parameter.

    If 'temporal navigation' is activated, this will be the result for the currently viewed 'start time'.
    This will be interpolated if necessary.

    If 'temporal navigation' is not active, then this will give the first result instead.

    Parameter can use double quotes in the style "parameter" or not.


    <h2>Example usage:</h2>
    <ul>
      <li>wntr_result_at_current_time( pressure ) -> 13</li>
      <li>wntr_result_at_current_time( "head" ) -> 6.2</li>
    </ul>
    """

    if context.variable("map_start_time") is None:
        return column[0]
    map_start_time = context.variable("map_start_time").toSecsSinceEpoch()
    animation_start_time = context.variable("animation_start_time").toSecsSinceEpoch()

    report_timestep = 3600

    timestep = (map_start_time - animation_start_time) / report_timestep

    if timestep < 0 or math.floor(timestep) + 1 > len(column):
        return None

    start_value = column[math.floor(timestep)]
    end_value = column[math.ceil(timestep)]

    return start_value + (timestep - math.floor(timestep)) * (end_value - start_value)
