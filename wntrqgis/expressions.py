import math

from qgis.core import qgsfunction

import wntrqgis.interface

GROUP = "Water Network Tools for Resilience"


# qgis 3.28 errors if 'feature' and 'parent' are not included
@qgsfunction(group=GROUP)
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


@qgsfunction(group=GROUP)
def wntr_check_pattern(pattern, feature, parent, context):  # noqa ARG001
    """
    Checks if the input is a valid pattern string.
    A valid pattern string is a space-separated list of numbers, e.g. "1 2 3 4".
    An empty string is also considered valid, as it means no pattern is defined.

    If the input is valid, it returns True; otherwise, it returns False.

    <h2>Example usage:</h2>
    <ul>
      <li>wntr_check_pattern('1 2 3 4') -> true</li>
      <li>wntr_check_pattern('x y z') -> false</li>
    </ul>
    """

    try:
        pattern = wntrqgis.interface._Patterns.read_pattern(pattern)  # noqa: SLF001
    except ValueError:
        return False

    if pattern is None:
        return None
    else:
        return True


@qgsfunction(group=GROUP)
def wntr_check_curve(curve):
    """
    Checks if the input is a valid curve string.
    A valid curve string is a list of tuples, e.g. "[(1,2), (3,4)]".
    An empty string is also considered valid, as it means no curve is defined.
    If the input is valid, it returns True; otherwise, it returns False.

    <h2>Example usage:</h2>
    <ul>
      <li>wntr_check_curve('[(1,2), (3,4)]') -> true</li>
      <li>wntr_check_curve('(1,2), (3,4)') -> true</li>
      <li>wntr_check_curve('(1,2)') -> true</li>
      <li>wntr_check_curve('(x,y)') -> false</li>
    </ul>
    """
    try:
        curve = wntrqgis.interface._Curves.read_curve(curve)  # noqa: SLF001
    except wntrqgis.interface.CurveReadError:
        return False

    if curve is None:
        return None
    else:
        return True
