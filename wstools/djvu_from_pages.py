#! /usr/bin/env python3

import argparse
import logging


import utils.file_utils as FU
import utils.djvu_utils as DJVU


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-d', '--directory', required=True,
                        help='The directory to find the pages in')
    parser.add_argument('-o', '--output', required=True,
                        help='The output DjVu file')
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    files = FU.get_dir_list_with_exts(args.directory, [".djvu"])
    print(files)
    files.sort()
    DJVU.create_djvu_from_pages(files, args.output)

if __name__ == "__main__":
    main()