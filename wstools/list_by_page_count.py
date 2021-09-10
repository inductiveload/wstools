#! /usr/bin/env python3

import argparse
import logging

import pywikibot
import pywikibot.proofreadpage


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-c', '--categories', nargs="+",
                        help='The categories to search')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)


    site = pywikibot.Site("en", "wikisource")

    indexes = []

    for c in args.categories:

        cat = pywikibot.page.Category(site, c)

        for member in site.categorymembers(cat):

            if member.namespace() == "Index:":
                print (member.title(with_ns=False))

                index = pywikibot.proofreadpage.IndexPage(site, member.title())

                num_pages = index.num_pages

                indexes.append({
                    'index': index,
                    'num': num_pages
                    })

    indexes.sort(key=lambda i: i['num'])


if __name__ == "__main__":
    main()