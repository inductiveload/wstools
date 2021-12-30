#! /usr/bin/env python3

import argparse
import logging


import os
import pywikibot
import pdf2image


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='show debugging information')
    parser.add_argument('-f', '--file', required=True,
                        help='The filename')
    parser.add_argument('-p', '--page', type=int, required=True,
                        help='')
    parser.add_argument('-o', '--output-dir', required=True,
                        help='The output dir')
    parser.add_argument('-d', '--dpi', type=int, default=500,
                        help='The DPI to render at')

    args = parser.parse_args()

    site = pywikibot.Site('en', 'wikisource')

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    file = pywikibot.FilePage(site, 'File:' + args.file)

    print(file)

    local_filename = '/tmp/dlfile.pdf'

    if not os.path.isfile(local_filename):
        ok = file.download(local_filename)
        assert(ok)

    print(f'File downloaded to {local_filename}')

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir, exist_ok=True)

    pdf2image.convert_from_path(local_filename,
                                dpi=args.dpi,
                                output_folder=args.output_dir,
                                first_page=args.page,
                                last_page=args.page,
                                fmt='jpg'
                                )


if __name__ == "__main__":
    main()
