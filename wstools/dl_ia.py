#! /usr/bin/env python3
"""
Download utility for Internet Archive scans
"""

import argparse
import logging
import os
import dotenv

import utils.ia_source as IASRC
import utils.source


def download(ia_id, output_dir, skip_existing=False, skip_djvu=False):

    print(output_dir)
    if os.path.isdir(output_dir) and skip_existing:
        return True

    src = IASRC.IaSource(ia_id)

    if skip_djvu and src.has_djvu():
        logging.debug("Have DJVU at IA")
        return False

    zip_fo = src.get_jp2_zip()

    if zip_fo:
        logging.debug(f"Extracting ZIP to {output_dir}")
        utils.source.extract_zip_to(zip_fo, output_dir)
        logging.debug("Extraction complete.")

    return True


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

    download(args.id, args.output_dir, args.skip_existing)


if __name__ == "__main__":
    main()
