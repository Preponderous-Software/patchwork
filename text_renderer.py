defaultFilled = "#"
defaultEmpty = "."

def renderLocations(locations, filled=defaultFilled, empty=defaultEmpty):
    """
    Render locations as a grid of text, with x increasing to the right and y increasing
    downwards, as in the Pygame window. The grid is sized from the locations themselves, and
    any cell in it that has no location is shown as empty. Cells are separated by a space,
    since a character in a terminal is about twice as tall as it is wide.

    Args:
        locations (list): The locations to render, each with get_x() and get_y()
        filled (str): The text for a cell that has a location
        empty (str): The text for a cell that has no location

    Returns:
        str: One line per row, without a trailing newline, or "" if there are no locations
    """
    occupied = {(location.get_x(), location.get_y()) for location in locations}
    if not occupied:
        return ""
    width = max(x for x, y in occupied) + 1
    height = max(y for x, y in occupied) + 1
    rows = []
    for y in range(height):
        rows.append(" ".join(filled if (x, y) in occupied else empty for x in range(width)))
    return "\n".join(rows)
