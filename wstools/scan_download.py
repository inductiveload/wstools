#! /usr/bin/env python3

import argparse
import logging

from xlsx2csv import Xlsx2csv
from io import StringIO
import csv
import os
import subprocess
import utils.ht_source


def parse_header_row(hr):

    mapping = {}

    for i, col in enumerate(hr):
        mapping[col.lower()] = i

    return mapping


def handle_row(r, args):

    print(r)

    if r['source'] == "ht":

        o_dir, _ = os.path.splitext(r['file'])

        utils.ht_source.dl_to_directory(r['id'], o_dir,
                                        skip_existing=args.skip_existing,
                                        make_dirs=True)

    else:
        raise ValueError("Unknown source: {}".format(r['source']))


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--data_file', required=True,
                        help='The data file')
    parser.add_argument('-r', '--rows', type=int, nargs="+",
                        help='Rows to process (1-indexed, same as in spreadsheet)')
    parser.add_argument('-s', '--skip_existing', action='store_true',
                        help='Skip files we already have')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # requests_cache.install_cache('downloadscans')

    output = StringIO()

    Xlsx2csv(args.data_file, skip_trailing_columns=True,
             skip_empty_lines=True, outputencoding="utf-8").convert(output)

    output.seek(0)

    reader = csv.reader(output, delimiter=',', quotechar='"')

    head_row = next(reader)
    col_map = parse_header_row(head_row)

    row_idx = 1

    for row in reader:
        row_idx += 1

        if args.rows is not None and row_idx not in args.rows:
            logging.debug("Skip row {}".format(row_idx))
            continue

        mapped_row = {}

        for col in col_map:
            mapped_row[col.lower()] = row[col_map[col]].strip()

        if "dl" in mapped_row and mapped_row["dl"].lower() in ["n", "no"]:
            logging.debug("Skipping row DL: {}".format(row_idx))
            continue

        handle_row(mapped_row, args)


if __name__ == "__main__":
    main()
