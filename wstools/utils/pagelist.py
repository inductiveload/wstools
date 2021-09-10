
def RepresentsInt(s):
    try:
        int(s)
        return True
    except ValueError:
        return False


class PageRange():

    def __init__(self, start, number, form, length):
        self.start = start
        self.end = start + length - 1
        self.number = number
        self.form = form

    def to_str(self, offset):

        def adj(n):
            return max(1, n - offset)

        start = adj(self.start)
        end = adj(self.end)

        if self.form == "numeric":
            return "{}={}".format(start, self.number)
        elif self.form in ["roman", "highroman"]:
            s = "{}={}".format(start, self.number)

            if start == end:
                s += "\n{}={}".format(start, self.form)
            else:
                s += "\n{}to{}={}".format(start, end, self.form)
            return s
        else:
            if start == self.end:
                return "{}=\"{}\"".format(start, self.number)

            return "{}to{}=\"{}\"".format(start, end, self.number)

    def length(self):
        return self.end - self.start + 1


class PageList():

    def __init__(self):
        self.ranges = []
        self.page = 0
        self.title_index = None

    @staticmethod
    def _roman_to_int(s):

        try:
            rom_val = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
            int_val = 0
            for i in range(len(s)):
                if i > 0 and rom_val[s[i]] > rom_val[s[i - 1]]:
                    int_val += rom_val[s[i]] - 2 * rom_val[s[i - 1]]
                else:
                    int_val += rom_val[s[i]]
            return int_val
        except KeyError:
            pass

        return None

    def to_pagelist_tag(self, offset):

        s = "<pagelist\n"
        s += "\n".join(r.to_str(offset) for r in self.ranges)
        s += "\n/>"
        return s

    def _fix_missing_first_pages(self, form):
        """
        Fix pageranges like:
          1to9=–
          10=2
        to become:
          1to8=–
          9=1
        """

        range_before_first_numeric = None
        first_numeric_range = None

        range_before_first_numeric = self.ranges[0]
        for r in self.ranges[1:]:
            if r.form == form:
                first_numeric_range = r
                break

            range_before_first_numeric = r

        if (first_numeric_range is not None and
                range_before_first_numeric.form == "string" and
                range_before_first_numeric.number == "–"):

            offset = first_numeric_range.number - 1

            # can't compensate by more than the number of blank pages
            if offset > range_before_first_numeric.length():
                offset = range_before_first_numeric.length()

            first_numeric_range.start -= offset
            first_numeric_range.number -= offset
            range_before_first_numeric.end -= offset

    def _clear_empty_ranges(self):

        self.ranges = [r for r in self.ranges if r.length() > 0]

    def clean_up(self):
        # attempt one each of roman and numeric
        self._fix_missing_first_pages('roman')
        self._fix_missing_first_pages('numeric')
        self._clear_empty_ranges()

    def append(self, number):

        self.page += 1

        form = "numeric"

        from_rom = self._roman_to_int(number.upper())

        if from_rom is not None:
            form = "roman"
            number = from_rom
        elif RepresentsInt(number):
            form = "numeric"
            number = int(number)
        else:
            form = "string"

        if number == "Title":
            self.title_index = self.page

        if not self.ranges:
            self.ranges.append(PageRange(self.page, number, form, 1))

        else:

            last_range = self.ranges[-1]

            # a new int, see if we can slot it in
            if (last_range.form == form and
                    RepresentsInt(number) and RepresentsInt(last_range.number)):

                last = int(last_range.number) + (last_range.end - last_range.start)
                this = int(number)

                if this == last + 1:
                    # extend
                    last_range.end += 1
                else:
                    # discontinuous
                    self.ranges.append(PageRange(self.page, number, form, 1))
            else:
                # not an int
                if last_range.form == form and last_range.number == number:
                    # extend
                    last_range.end += 1
                else:
                    # start a new range
                    self.ranges.append(PageRange(self.page, number, form, 1))
