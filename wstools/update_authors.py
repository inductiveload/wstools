#! /usr/bin/env python3

import argparse
import logging

import pywikibot


class AuthorLister():

    def __init__(self, site):
        self.site = site

    def list(self):

        return []


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')

    args = parser.parse_args()

    site = pywikibot.Site('wikisource', 'en')

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    lister = AuthorLister(site)

    alist = lister.list()
    print(alist)


if __name__ == "__main__":
    main()
