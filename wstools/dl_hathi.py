#! /usr/bin/env python3
"""
Download utility for HathiTrust works
"""

import argparse
import logging
import os
import dotenv

import utils.ht_api as HTAPI
import utils.ht_source as HTSRC

import utils.source


def download(direct, ht_id, output_dir, skip_existing=False, skip_images=False,
             proxy=False, include_pages=None, exclude_pages=None):

    dapi = HTAPI.DataAPI(client_key=None, client_secret=None, proxies=proxy,
                         secure=True)

    rq = dapi.rsession.get("https://api.ipify.org?format=json")
    logging.debug(rq.content.decode('utf-8'))

    ht_source = HTSRC.HathiSource(dapi, ht_id)
    ht_source.direct_download = direct

    utils.source.dl_to_directory(ht_source, output_dir,
                                 skip_existing=skip_existing,
                                 images=not skip_images,
                                 ocr=False,
                                 make_dirs=True,
                                 include_pages=include_pages,
                                 exclude_pages=exclude_pages)
    return output_dir

def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--id', type=str, required=True,
                        help="Hathi ID, e.g. umn.31951002135568t")
    parser.add_argument('-o', '--output-dir',
                        help='Output dir')
    parser.add_argument('-s', '--skip-existing', action='store_true',
                        help='Skip files we already have')
    parser.add_argument('-I', '--skip-images', action='store_true',
                        help='Skip image download')
    parser.add_argument('-p', '--proxy', action='store_true',
                        help='Use a proxy')
    parser.add_argument('-D', '--direct', action='store_true',
                        help='Use the direct download method')

    args = parser.parse_args()

    dotenv.load_dotenv()

    if not args.output_dir:
        odir = os.getenv('WSTOOLS_OUTDIR')

        if odir:
            args.output_dir = os.path.join(odir,
                                           utils.source.sanitise_id(args.id))

    if not args.output_dir:
        raise ValueError("Need an output dir")

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)

    download(args.direct, args.id, args.output_dir, args.skip_existing,
             args.skip_images, args.proxy)


if __name__ == "__main__":
    main()
