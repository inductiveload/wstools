#! /usr/bin/env python3

import argparse
import logging


import os
import pywikibot


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--file',
                        help='The file to upload')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='Dry run?')
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    site = pywikibot.Site('commons', 'commons')

    fhead, ftail = os.path.split(args.file)
    fileroot, ext = os.path.splitext(ftail)

    info_file = os.path.join(fhead, 'info', fileroot + '.txt')

    with open(info_file, 'r') as info:

        destname = info.readline().lstrip(':').strip()

        itext = info.read()

    itext += "[[Category:Uploads for 維基小霸王]]"

    print(destname)
    print(itext)

    filepage = pywikibot.FilePage(site, destname)

    summary = "Uploading file from [[User:維基小霸王]] (original filename: {}".format(ftail)

    if not args.dry_run:
        site.upload(
            filepage=filepage,
            source_filename=args.file,
            comment=summary,
            text=itext,
            chunk_size=1 * 1024 * 1024,
            asynchronous=True
        )


if __name__ == "__main__":
    main()