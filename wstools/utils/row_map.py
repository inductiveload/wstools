import utils.range_selection
import os
import csv
import xlsx2csv
from io import StringIO
import logging

class ColumnMap():

    def __init__(self, head_row):
        self.mapping = {}

        for i, col in enumerate(head_row):
            self.mapping[col.lower()] = i

    def __iter__(self):

        for col in self.mapping:
            yield col, self.mapping[col]


class DataRow():

    def __init__(self, col_map, row, index=None):

        self.index = index

        mapped_row = {}

        for col_name, col_index in col_map:
            value = row[col_index].strip()
            mapped_row[col_name] = value
        self.r = mapped_row

    def get(self, key):

        if key not in self.r:
            return None

        v = self.r[key]
        if isinstance(v, str):
            return v.strip()

        return v

    def set(self, key, value):
        self.r[key] = value

    def set_default(self, key, value):
        if key not in self.r:
            self.r[key] = value

    def get_bool(self, key, default):

        v = self.get(key)

        if not v:
            return default

        return v[0].lower() in ['y', 't', '1']

    def dump(self):
        s = ''
        for key in self.r:
            s += f'{key}: {self.r[key]}\n'
        return s

    def apply(self, key, func):
        if key not in self.r:
            return

        self.r[key] = func(self.r[key])

    def get_split(self, key, split_on):

        v = self.get(key)
        if not v:
            return []

        return [x.strip() for x in v.split(split_on)]

    def get_ranges(self, key):

        v = self.get_split(key, ',')

        if not v:
            return []

        return utils.range_selection.get_range_selection(v)

def get_rows(infile, rows):

    _, ext = os.path.splitext(infile)

    print(ext, infile)
    if ext == ('.xlsx'):
      output = StringIO()

      xlsx2csv.Xlsx2csv(infile, skip_trailing_columns=True,
              skip_empty_lines=True, outputencoding="utf-8").convert(output)

      output.seek(0)
    elif ext == '.csv':
      output = open(infile, 'rb')

    reader = csv.reader(output, delimiter=',', quotechar='"')

    head_row = next(reader)
    col_map = utils.row_map.ColumnMap(head_row)

    if rows:
      rows = utils.range_selection.get_range_selection(rows)

    mapped_rows = []
    row_idx = 1
    for row in reader:
      row_idx += 1
      if rows and row_idx not in rows:
        #   logging.debug("Skip row {}".format(row_idx))
          continue

      mapped_rows.append(
        utils.row_map.DataRow(col_map, row, index=row_idx)
      )

    return mapped_rows