#! /usr/bin/env python3
"""
Download utility for Internet Archive scans
"""

import argparse
from itertools import count
import logging
import os
import dotenv

import utils.ia_source as IASRC
import utils.source
import utils.file_utils
import utils.djvu_utils
import utils.range_selection

import tqdm
import requests


def file_is_excluded(zipinfo, include_indexes, exclude_indexes):

    if zipinfo.is_dir():
        return False

    root, _ = os.path.splitext(zipinfo.filename)

    file_index = root.split('_')[-1].lstrip('0')
    if file_index == '':
        file_index = 0

    file_index = int(file_index)

    if include_indexes:
        if file_index not in include_indexes:
            return True

    return file_index in exclude_indexes

def count_files_in_dir(d) -> int:
    return len([name for name in os.listdir(d) if os.path.isfile(os.path.join(d, name))])

def download_jp2s(ia_src, output_dir, include_pages, exclude_pages, skip_existing):

    zip_name = ia_src.get_jp2_zip_name()
    zip_root, _ = os.path.splitext(zip_name)
    zip_outdir = os.path.join(output_dir, zip_root)

    if (skip_existing and
        os.path.isdir(zip_outdir) and
        count_files_in_dir(zip_outdir) > 1): # hax
        logging.debug(f'Output dir appears to exist in: {zip_outdir}')
        return output_dir

    exclude_indexes = ia_src.get_file_indexes_not_in_output()

    if exclude_pages:
        exclude_indexes += exclude_pages

    zip_fo = ia_src.get_jp2_zip()

    if zip_fo:
        logging.debug(f"Extracting ZIP to {output_dir}")

        if exclude_indexes:
            def excluder(zip_info):
                return file_is_excluded(zip_info, include_pages,
                                        exclude_indexes)
        else:
            excluder = None

        utils.file_utils.extract_zip_to(zip_fo, output_dir, excluder)
        logging.debug("Extraction complete.")

        zip_fo.close()

    return output_dir


def download_jpgs(ia_src, output_dir, include_pages, exclude_pages, scale=3):
    jpgs = ia_src.get_jpg_list(scale)

    # first, filter the list for includes:
    if include_pages:
        jpgs = [j for j in jpgs if j['index'] in include_pages]

    # filter the list for exclusions
    if exclude_pages:
        jpgs = [j for j in jpgs if j['index'] not in exclude_pages]

    for img_info in tqdm.tqdm(jpgs):

        r = requests.get(img_info['url'])
        r.raise_for_status()

        ofile = os.path.join(output_dir, img_info['name'])
        with open(ofile, 'wb') as ofo:
            ofo.write(r.content)


def download_djvu(ia_src, output_dir, include_pages, exclude_pages):

    djvu_fo = ia_src.get_djvu()

    djvu_file = os.path.join(output_dir, ia_src.id + '.djvu')
    with open(djvu_file, 'wb') as ofo:
        djvu_fo.seek(0)
        ofo.write(djvu_fo.read())

    utils.djvu_utils.strip_pages(djvu_file, include_pages, exclude_pages)

    return djvu_file

def download(ia_id, output_dir, skip_existing=False,
             skip_djvu=False, get_images=False,
             include_pages=[], exclude_pages=[]):

    # if os.path.isdir(output_dir) and skip_existing:
    #     return True

    os.makedirs(output_dir, exist_ok=True)

    src = IASRC.IaSource(ia_id)

    if skip_djvu and (include_pages or exclude_pages):
        logging.debug('Cannot skip DJVU if adjusting the page ranges')
        skip_djvu = False

    djvu = src.get_file_url('DjVu')

    if skip_djvu and djvu is not None:
        logging.debug("Have DJVU at IA, skipping download")
        return djvu

    # download_jpgs(src, output_dir, include_pages, exclude_pages
    if djvu is not None and not get_images:
        # get DJVU if we can and save a ton of work
        return download_djvu(src, output_dir, include_pages, exclude_pages)

    # do it from scratch
    # this can still skip the download if needed
    return download_jp2s(src, output_dir, include_pages, exclude_pages,
                         skip_existing=skip_existing)


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--id', type=str, required=True,
                        help="IA ID, e.g. worksofthomashea02heariala")
    parser.add_argument('-o', '--output-dir',
                        help='Output dir')
    parser.add_argument('-s', '--skip-existing', action='store_true',
                        help='Skip files we already have')
    parser.add_argument('-p', '--pages',
                        help='Pages to download')
    parser.add_argument('-I', '--get-images', action='store_true',
                        help='Get images only')
    parser.add_argument('-f', '--format',
                        help='Preferred format (jpg, jp2)')

    args = parser.parse_args()

    dotenv.load_dotenv()

    if not args.output_dir:
        odir = os.getenv('WSTOOLS_OUTDIR')

        if odir:
            args.output_dir = os.path.join(odir,
                                           utils.source.sanitise_id(args.id))

    if not args.output_dir:
        raise ValueError("Need an output dir")

    if args.pages:
        args.pages = utils.range_selection.get_range_selection(args.pages)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)

    download(args.id, args.output_dir,
             skip_existing=args.skip_existing,
             get_images=args.get_images,
             include_pages=args.pages,
             format=args.format)


if __name__ == "__main__":
    main()
