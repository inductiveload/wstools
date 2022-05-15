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
import concurrent.futures



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


def download_urls(urls, destinations, threads=10, progress=None, skip_existing=False):
    if len(urls) != len(destinations):
        print(len(urls), len(destinations))
        raise ValueError("Each URL must have a destination")

    def download_file(url, dest_path):

        if skip_existing and os.path.isfile(dest_path) and os.stat(dest_path).st_size > 0:
            logging.debug(f"Skipping existing file: {url}")
            pass
        else:
            logging.debug(f"Downloading file: {url}")
            with requests.get(url) as response:
                response.raise_for_status()
                with open(dest_path, 'wb') as f:
                    f.write(response.content)

        progress.update(n=1)

    dls = zip(urls, destinations)

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:

        future_to_url = {executor.submit(download_file, dl[0], dl[1]): dl for dl in dls}

        for future in concurrent.futures.as_completed(future_to_url):

            url = future_to_url[future]
            try:
                future.result()
            except Exception as exc:
                print('%r generated an exception: %s' % (url, exc))
                raise RuntimeError

def filter_indexes(url_infos, include_indexes=[], exclude_indexes=[]):

    def filter_match(url_info):
        index = url_info['index']
        if include_indexes:
            if index not in include_indexes:
                return False

        if exclude_indexes:
            if index in exclude_indexes:
                return False

        return True

    return [ui for ui in url_infos if filter_match(ui)]


def download_from_url_list(ia_src, list_function, output_dir, include_pages, exclude_pages, skip_existing):

    if not os.path.isdir(output_dir):
        raise RuntimeError(f'{output_dir} is not a directory')

    exclude_indexes = ia_src.get_file_indexes_not_in_output()

    if exclude_pages:
        exclude_indexes += exclude_pages

    url_infos = list_function()
    url_infos = filter_indexes(
            url_infos, include_indexes=include_pages, exclude_indexes=exclude_pages)

    def get_destination(url_info):
        index = url_info['index']
        ext = url_info['ext']
        return os.path.join(output_dir, f'{ia_src.id}_{index:04}{ext}')

    urls = [url_info['url'] for url_info in url_infos]
    destinations = [get_destination(url_info) for url_info in url_infos]

    progress = tqdm.tqdm(urls)

    download_urls(urls, destinations, progress=progress, skip_existing=skip_existing)
    return output_dir

def download_jp2s(ia_src, output_dir, include_pages=[], exclude_pages=[], skip_existing=False):
    return download_from_url_list(
        ia_src,
        ia_src.get_jp2_list,
        output_dir,
        include_pages,
        exclude_pages,
        skip_existing)

def download_jpgs(ia_src, output_dir, include_pages=[], exclude_pages=[], skip_existing=False):
    return download_from_url_list(
        ia_src,
        ia_src.get_jpg_list,
        output_dir,
        include_pages,
        exclude_pages,
        skip_existing)

def download_djvu(ia_src, output_dir, include_pages, exclude_pages):

    djvu_fo = ia_src.get_djvu()

    djvu_file = os.path.join(output_dir, ia_src.id + '.djvu')
    with open(djvu_file, 'wb') as ofo:
        djvu_fo.seek(0)
        ofo.write(djvu_fo.read())

    utils.djvu_utils.strip_pages(djvu_file, include_pages, exclude_pages)

    return djvu_file

def download(src, output_dir, skip_existing=False,
             skip_djvu=False, get_images=False,
             include_pages=[], exclude_pages=[]):

    # if os.path.isdir(output_dir) and skip_existing:
    #     return True

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

    os.makedirs(args.output_dir, exist_ok=True)

    src = IASRC.IaSource(args.id)

    # download(src, args.output_dir,
    #          skip_existing=args.skip_existing,
    #          get_images=args.get_images,
    #          include_pages=args.pages,
    #          format=args.format)

    download_jp2s(src, args.output_dir)

if __name__ == "__main__":
    main()
