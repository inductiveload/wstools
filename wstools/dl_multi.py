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
import shutil

import subprocess

import dl_book

import utils.ht_source as HTS
import utils.range_selection
import utils.row_map


def get_conversion_opts(dl):

    if dl.src == 'ht':
        return ["-b", ".png"]

    if dl.src == 'ia':
        return []

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

        dls.append(dl_book.DlDef('ht', htid.strip(), fn.strip()))

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
    col_map = utils.row_map.ColumnMap(head_row)

    row_idx = 1

    dls = []
    for row in reader:
        row_idx += 1

        if rows and len(rows) and row_idx not in rows:
            logging.debug(f'Skipping row {row_idx}')
            continue

        mapped_row = utils.row_map.DataRow(col_map, row)

        # skip downloads if needed
        if not mapped_row.get_bool('dl', True):
            logging.debug(f'Skipping DL for row {row_idx}')
            continue

        srcid = mapped_row.get('id')

        filename = mapped_row.get('file')

        if not filename:
            filename = mapped_row.get('filename')
        if not filename:
            filename = mapped_row.get('id')

        source = mapped_row.get('source')

        if source == 'ht':
            srcid = HTS.normalise_id(srcid)

        dl_def = dl_book.DlDef(source, srcid, filename)

        if mapped_row.get('access') == 'us':
            dl_def.use_proxy = True

        if mapped_row.get_bool('dl', False):
            dl_def.force_dl = True

        if mapped_row.get_bool('regen', False):
            dl_def.regenerate = True

        dl_def.exclude_pages = mapped_row.get_ranges('rm_pages')
        dl_def.include_pages = mapped_row.get_ranges('only_pages')

        dls.append(dl_def)
    return dls


def main():

    parser = argparse.ArgumentParser(description='Download and convert')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='show debugging information')
    parser.add_argument('-f', '--dl-file', required=True,
                        help='File-based download list')
    parser.add_argument('-D', '--skip_dl', action='store_true',
                        help='Skip download')
    parser.add_argument('-p', '--proxy', action='store_true',
                        help='Use a proxy')
    parser.add_argument('-r', '--rows', nargs='+',
                        help='Rows (only for XLSX)')
    parser.add_argument('-S', '--size', type=int,
                        help='Target DJVU size')
    parser.add_argument('-s', '--skip-existing', action='store_true',
                        help='Skip files we already have a DJVU for')
    parser.add_argument('-T', '--threads', type=int,
                        help='Number of threads to use for conversion')
    parser.add_argument('-x', '--sources', nargs='+',
                        help='Sources to use (e.g. IA, HT), skip others. Default: all')
    parser.add_argument('-C', '--skip-convert', action='store_true',
                        help='Skip conversion stage and download only')
    parser.add_argument('-H', '--hathi-direct', action='store_true',
                        help='Use the direct download method for Hathi')

    args = parser.parse_args()

    dotenv.load_dotenv()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)

    dls = []

    rows = utils.range_selection.get_range_selection(args.rows)

    if args.dl_file:

        if args.dl_file.endswith('.xlsx'):
            dls = dls_from_xlsx(args.dl_file, rows)
        else:
            with open(args.dl_file, "r") as infile:
                dls = dls_from_text(infile)

    for dl in dls:
        logging.debug(f'{dl.id} → {dl.filename}')

    basedir = os.getenv('WSTOOLS_OUTDIR')
    tmp_dir = "tmp"
    keep_temp = False
    skip_existing = args.skip_existing
    threads = args.threads or int(multiprocessing.cpu_count() * 0.8)

    if args.sources:
        args.sources = [x.lower() for x in args.sources]

    for dl in dls:

        if args.sources and len(args.sources) > 0 and dl.src.lower() not in args.sources:
            logging.debug(f'Skipping source: {dl.src}')
            continue

        root, ext = os.path.splitext(dl.filename)

        sanitised_id = dl.id.replace('/', '_')

        if ext.lower() in ['.pdf', '.djvu', '.tiff']:
            odir = root
        elif dl.filename:
            odir = dl.filename
        else:
            odir = sanitised_id

        dl_dir = os.path.join(basedir, odir)

        output_file = os.path.join(basedir, odir + '.djvu')

        if os.path.isfile(output_file):
            if skip_existing:
                logging.info(f'Skip existing file: {output_file}')
                continue
            else:
                os.remove(output_file)

        downloaded = False
        if args.skip_dl:
            downloaded = True
        else:
            # this is the images
            dl.skip_existing = skip_existing
            dl.hathi_direct = args.hathi_direct
            downloaded = dl_book.do_download(dl, dl_dir)

        # override
        if args.proxy is not None:
            dl.use_proxy = args.proxy

        if not args.size:
            args.size = os.getenv('CONVERT_DEFAULT_SIZE')

        if (downloaded and
                os.path.isfile(downloaded) and
                os.path.splitext(downloaded)[1] in ['.djvu', '.pdf']):
            logging.debug('Skipping conversion because '
                          f'the source provided the file: {downloaded}')
            logging.debug(f'Moving to {output_file}')
            shutil.move(downloaded, output_file)
        elif args.skip_convert:
            logging.debug('Skipping conversion due to --skip-convert')
        elif not downloaded:
            logging.debug("Skipping convert: images not downloaded OK")
        else:
            cmd = ["./make_document.py",
                   "-i", dl_dir,
                   "-o", output_file,
                   "-t", os.path.join(basedir, tmp_dir),
                   "-R",
                   "-T", str(threads)]

            # handled at the download step
            # if dl.exclude_pages:
            #     cmd += ['--exclude_pages'] + [str(x) for x in dl.exclude_pages]

            if keep_temp:
                cmd.append("-D")

            if dl.filename:
                cmd + ['-o', dl.filename]

            cmd += get_conversion_opts(dl)

            if args.size:
                cmd += ["-s", str(args.size)]

            # very verbose also converts in verbose mode
            if args.verbose > 1:
                cmd.append("-v")

            logging.debug(cmd)
            subprocess.call(cmd)


if __name__ == "__main__":
    main()
