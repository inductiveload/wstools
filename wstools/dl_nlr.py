#! /usr/bin/env python3
"""
Download utility for NLR works
"""

import argparse
import logging

import os
import subprocess

import tempfile
import requests


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--id', type=str, required=True,
                        help="NLR ID, e.g. pm000041257")
    parser.add_argument('-o', '--output_dir', required=True,
                        help='Output dir')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir, exist_ok=True)

    tmp_file, tmp_file_path = tempfile.mkstemp(suffix=".pdf", prefix=args.id)

    url = "https://vivaldi.nlr.ru/{}/file".format(args.id)

    logging.debug("Downloading: {}".format(url))

    req = requests.get(url)

    req.raise_for_status()

    with open(tmp_file, 'wb') as f:
        f.write(req.content)

    logging.debug("PDF downloaded and written")

    cmd = ["pdfimages", "-j", tmp_file_path,
           os.path.join(args.output_dir, args.id)]

    logging.debug(cmd)
    subprocess.call(cmd)

    os.remove(tmp_file_path)


if __name__ == "__main__":
    main()