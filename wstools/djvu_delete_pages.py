#! /usr/bin/env python3

import argparse
import logging

import subprocess
import utils.range_selection
import tqdm


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--file',
                        help='The file to delete pages from')
    parser.add_argument('-p', '--pages', nargs='+',
                        help='The pages to delete')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    pages = utils.range_selection.get_range_selection(args.pages)
    pages.sort(reverse=True)

    for p in tqdm.tqdm(pages):
        cmd = ['djvm', '-d', args.file, str(p)]
        ret = subprocess.call(cmd)

        if ret != 0:
            raise RuntimeError(f"djvm -d failed with cmd: {cmd}")


if __name__ == "__main__":
    main()