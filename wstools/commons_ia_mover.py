#! /usr/bin/env python3
# Script to move Fae IA imports
import argparse
import logging

import os

import pywikibot
from pywikibot import textlib

PREFIX = "Hardwicke's Science-Gossip"
DATA = [
    ("https://www.archive.org/download/hardwickesscienc291893", "Volume 29"),
]
REASON = "Move to include volume number instead of IA ID"
CATS = [
    "Hardwicke's Science-Gossip"
]

# DATA = [
#     ("https://www.archive.org/download/hardwickesscienc{v:02}cook".format(v=i),
#      "Volume {v}".format(v=i))
#         for i in range(25, 30)
#     ]


def main():


    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)


    com_site = pywikibot.Site("commons", "commons")


    for d in DATA:

        ia_id = d[0].split("/")[-1]

        print(ia_id)

        pages = []

        for res in com_site.search("\"(IA {})\"".format(ia_id)):

            if "(IA {})".format(ia_id) in res.title():
                pages.append(res)

        if len(pages) != 1:
            raise RuntimeError("Didn't find a single page, found {}".format(len(pages)))

        page = pages[0]

        print(page.title())

        _, ext = os.path.splitext(page.title())
        new_title = "File:" + PREFIX + " - " + d[1] + ext

        text = page.text
        cats = textlib.getCategoryLinks(
            text, page.site)

        new_cats = []
        for cat in CATS:

            catpl = pywikibot.Category(page.site, cat)

            if catpl in cats:
                pywikibot.output('{} is already in {}.'
                                 .format(page.title(), catpl.title()))
                continue

            pywikibot.output('Adding %s' % catpl.title(as_link=True, allow_interwiki=False))

            new_cats.append(catpl)

        if len(new_cats) > 0:

            cats += new_cats

            text = textlib.replaceCategoryLinks(
                        text, cats, site=page.site)

            if not args.dry_run:
                page.put(text, summary="Add categories: " + ", ".join(
                        [c.title(as_link=True, allow_interwiki=False) for c in new_cats]))

        if not args.dry_run:
            page.move(new_title,
                 reason=REASON)

        print(cats)

if __name__ == "__main__":
    main()