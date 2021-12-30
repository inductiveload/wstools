#! /usr/bin/env python3

import argparse
import logging


import dotenv

def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='show debugging information')
    parser.add_argument('-i', '--id',
                        help='The MassHist ID (e.g. 3)')
    parser.add_argument('-n', '--num-pages',
                        help='Number of pages')
    parser.add_argument('-o', '--outdir',
                        help='The output dir')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

if __name__ == "__main__":
    main()