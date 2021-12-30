#! /usr/bin/env python3

import argparse
import logging


import pywikibot
import pywikibot.proofreadpage
import io
import shutil


class Exporter():

    def __init__(self, ofo):
        self.ofo = ofo

    def export_page(self, page):
        self.ofo.write(f'=={page.title()}==\n')
        self.ofo.write(page.text + '\n')


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='show debugging information')
    parser.add_argument('-i', '--index',
                        help='The index')
    args = parser.parse_args()

    site = pywikibot.Site('en', 'wikisource')

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    if not args.index.startswith('Index:'):
        args.index = 'Index:' + args.index

    index = pywikibot.proofreadpage.IndexPage(site, args.index)

    ofo = io.StringIO()

    exporter = Exporter(ofo)

    for page in index.page_gen(only_existing=True):
        exporter.export_page(page)

    print(ofo.getvalue())

    with open('/tmp/file.txt', 'w') as fd:
        ofo.seek(0)
        shutil.copyfileobj(ofo, fd)


if __name__ == "__main__":
    main()
