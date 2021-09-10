#! /usr/bin/env python3

import argparse
import logging
import os
import multiprocessing
import re
from xlsx2csv import Xlsx2csv
from io import StringIO
import csv
import dotenv

import subprocess

import dl_hathi

import utils.ht_source as HTS


class DlDef():

    def __init__(self, src, id, filename):

        self.id = id
        self.filename = filename
        self.src = src

    def get_opts(self):

        if self.src == 'ht':
            return ["-b", ".png"]

        raise NotImplementedError


def dls_from_text(infile):

    dls = []
    for line in infile:
        line = line.strip()

        # skip blanks
        if not line:
            continue

        if re.match(r"^# *END *#$", line):
            break

        if (not line or line.startswith("#")):
            continue

        try:
            match = re.match(r"(.*?)\s+(.*)", line)
            htid = match.group(1)
            fn = match.group(2)
        except ValueError:
            print(line)
            raise

        dls.append(DlDef('ht', htid.strip(), fn.strip()))

    return dls


def parse_header_row(hr):

    mapping = {}

    for i, col in enumerate(hr):
        mapping[col.lower()] = i

    return mapping


def dls_from_xlsx(filename, rows):

    output = StringIO()

    Xlsx2csv(filename, skip_trailing_columns=True,
             skip_empty_lines=True, outputencoding="utf-8").convert(output)

    output.seek(0)

    reader = csv.reader(output, delimiter=',', quotechar='"')

    head_row = next(reader)
    col_map = parse_header_row(head_row)

    row_idx = 1

    dls = []
    for row in reader:
        row_idx += 1

        if rows and len(rows) and row_idx not in rows:
            logging.debug(f'Skipping row {row_idx}')
            continue

        mapped_row = {}
        for col in col_map:
            mapped_row[col.lower()] = row[col_map[col]].strip()

        # skip downloads if needed
        if 'dl' in mapped_row and mapped_row['dl'].lower() in ['n', 'no', '0', 'f']:
            logging.debug(f'Skipping DL for row {row_idx}')
            continue

        htid = row[col_map['id']].strip()

        if 'file' in mapped_row:
            filename = mapped_row['file']
        elif 'filename' in mapped_row:
            filename = mapped_row['filename']
        else:
            filename = mapped_row['id']

        source = mapped_row['source']

        if source == 'ht':
            htid = HTS.normalise_id(htid)

        dls.append(DlDef(source, htid, filename))

    logging.debug(dls)

    return dls


def main():

    parser = argparse.ArgumentParser(description='Download and convert')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--dl-file', required=True,
                        help='File-based download list')
    parser.add_argument('-D', '--skip_dl', action='store_true',
                        help='Skip download')
    parser.add_argument('-p', '--proxy', action='store_true',
                        help='Use a proxy')
    parser.add_argument('-r', '--rows', nargs='+',
                        help='Rows (only for XLSX)')

    args = parser.parse_args()

    dotenv.load_dotenv()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)

    dls = []

    if args.rows:
        rows = []

        for r in args.rows:
            m = re.match(r'(\d+)-(\d+)', r)

            if m:
                rows += range(int(m.group(1)), int(m.group(2)))
            else:
                rows.append(int(r))

    if args.dl_file:

        if args.dl_file.endswith('.xlsx'):
            dls = dls_from_xlsx(args.dl_file, rows)
        else:
            with open(args.dl_file, "r") as infile:
                dls = dls_from_text(infile)

    for dl in dls:
        print(f'{dl.id} → {dl.filename}')

    basedir = os.getenv('WSTOOLS_OUTDIR')
    tmp_dir = "tmp"
    skip_existing = True
    threads = int(multiprocessing.cpu_count() * 0.8)

    for dl in dls:

        root, ext = os.path.splitext(dl.filename)

        if ext.lower() in ['.pdf', '.djvu', '.tiff']:
            odir = root
        elif dl.filename:
            odir = dl.filename
        else:
            odir = dl.id.replace('/', '_')

        dl_dir = os.path.join(basedir, odir)

        if not args.skip_dl:

            if dl.src == 'ht':
                dl_hathi.download(dl.id, dl_dir, skip_existing=skip_existing,
                                  proxy=args.proxy)
            else:
                raise NotImplementedError

        cmd = ["./make_document.py",
               "-i", dl_dir,
               "-t", os.path.join(basedir, tmp_dir),
               "-R", "-T", str(threads)]

        if dl.filename:
            cmd + ['-o', dl.filename]

        cmd += dl.get_opts()

        # cmd += ["-k", "-s", "100"]

        if args.verbose:
            cmd.append("-v")
            print(cmd)

        subprocess.call(cmd)


if __name__ == "__main__":
    main()
