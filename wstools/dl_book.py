#! /usr/bin/env python3

import argparse
import logging
import dotenv

import dl_hathi
import dl_ia


class DlDef():
    def __init__(self, src, id, filename):
        self.src = src.lower()
        self.id = id
        self.filename = filename
        self.skip_existing = False
        self.use_proxy = False


def do_download(dl, dl_dir):

    if dl.src == 'ht':
        dl_hathi.download(dl.id, dl_dir, skip_existing=dl.skip_existing,
                          proxy=dl.use_proxy)
        return True
    elif dl.src == 'ia':
        return dl_ia.download(dl.id, dl_dir, skip_existing=dl.skip_existing, skip_djvu=True)
    else:
        raise NotImplementedError


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--id',
                        help='The source identifier')
    parser.add_argument('-s', '--src',
                        help='The source key (e.g. ia for Internet Archive)')
    parser.add_argument('-o', '--outdir',
                        help='The output dir')

    args = parser.parse_args()

    dotenv.load_dotenv()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)


if __name__ == "__main__":
    main()
