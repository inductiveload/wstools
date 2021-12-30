#! /usr/bin/env python3

import argparse
import logging

import os
import csv
import xlsx2csv
from io import StringIO

import utils.row_map
import utils.range_selection

def get_rows(infile, rows):

    _, ext = os.path.splitext(infile)

    if ext == ('.xlsx'):
      output = StringIO()

      xlsx2csv.Xlsx2csv(infile, skip_trailing_columns=True,
              skip_empty_lines=True, outputencoding="utf-8").convert(output)

      output.seek(0)
    elif ext == '.csv':
      output = open(infile, 'rb')

    try:
      reader = csv.reader(output, delimiter=',', quotechar='"')
    finally:
      output.close()

    head_row = next(reader)
    col_map = utils.row_map.ColumnMap(head_row)

    if rows:
      rows = utils.range_selection.get_range_selection(rows)

    mapped_rows = []
    row_idx = 0
    for row in reader:
      row_idx += 1
      if rows and row_idx not in rows:
          # logging.debug("Skip row {}".format(row_idx))
          continue

      mapped_rows.append(
        utils.row_map.DataRow(col_map, row)
      )

    return mapped_rows

class MsPage():

  def __init__(self, file, wdms, pagenum, pageindex) -> None:
    self.file = file
    self.wdms = wdms
    self.pagenum = pagenum
    self.pageindex = pageindex

class MsPageUploader():

  def __init__(self) -> None:
    pass

  def upload_page(self, page: MsPage):

def main():

  parser = argparse.ArgumentParser(description='')
  parser.add_argument('-v', '--verbose', action='count', default=0,
            help='show debugging information')
  parser.add_argument('-i', '-infile', required=True)

  args = parser.parse_args()

  log_level = logging.DEBUG if args.verbose else logging.INFO
  logging.basicConfig(level=log_level)

  rows = get_rows(args.infile, args.rows)

if __name__ == '__main__':
  main()