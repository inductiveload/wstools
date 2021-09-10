#! /usr/bin/env python3

import argparse
import logging

import pywikibot


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--filename',
                        help='The filename at Commons')
    parser.add_argument('-d', '--desat', action='store_true',
                        help='Desaturate')



    summary = "Processing image with process_m"




    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)


if __name__ == "__main__":
    main()