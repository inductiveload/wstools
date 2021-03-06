
import re


def get_range_selection(page_arr, last=None, unique=True):
    """
    From an array like 1, 2, 4-5, 6+2, 22-end, get a list of the
    individual pages
    """

    if not page_arr:
        return []

    if isinstance(page_arr, str):
        page_arr = [x.strip() for x in page_arr.split(',')]

    rows = []
    for r in page_arr:
        m = re.match(r'(\d+)([+-])(\d+)', r)

        if m:
            if m.group(2) == '-':

                if m.group(3) == 'end':
                    if last is not None:
                        rows += range(int(m.group(1)), last + 1)
                    else:
                        raise ValueError("Don't know the 'end' value")
                else:
                    rows += range(int(m.group(1)), int(m.group(3)) + 1)
            else:
                rows += range(int(m.group(1)),
                              int(m.group(1)) + int(m.group(3)) + 1)
        else:
            rows.append(int(r))

    # remove duplicates
    if unique:
        rows = list(dict.fromkeys(rows))

    return rows
