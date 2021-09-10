#! /usr/bin/env python3

import argparse
import logging


import pywikibot
import pywikibot.pagegenerators

import mwparserfromhell

import re


SNB = [
 "sidenotes begin",
]


class Replacer():

    def __init__(self):
        self.always = False

    def update(self, page, new_text, summary):

        if new_text != page.text:
            pywikibot.showDiff(page.text, new_text)

            if self.always:
                choice = 'y'
            else:
                choice = pywikibot.input_choice(
                        'Do you want to accept these changes?',
                        [('Yes', 'y'), ('No', 'n'), ('all', 'a')],
                        default='N')

            if choice == 'y' or choice == 'a':
                page.text = new_text
                page.save(summary)

                if choice == 'a':
                    self.always = True


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--index', required=True,
                        help='The Index to process')
    parser.add_argument('-r', '--reverse', action='store_true',
                        help='Reverse the sides (default: even page is left)')
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    site = pywikibot.Site('en', 'wikisource')

    page_gen = pywikibot.pagegenerators.PrefixingPageGenerator(
        site=site,
        namespace="Page",
        prefix=args.index
    )

    replacer = Replacer()

    summary = "Remove manual sidenotes begin width, and set a side"

    for page in page_gen:

        print(page.title())

        wikicode = mwparserfromhell.parse(page.text)
        templates = wikicode.filter_templates()

        num = int(re.sub(r'^.*/([0-9]+)$', r'\1', page.title()))

        snb = [x for x in templates if x.name.strip().lower() in SNB]

        print(snb)

        for o in snb:

            try:
                o.remove(1)
            except ValueError:
                pass
            try:
                o.remove(2)
            except ValueError:
                pass

            if (num % 2 == 0) == (not args.reverse):
                o.add('side', 'left')
            else:
                o.add('side', 'right')

        new_text = str(wikicode)

        replacer.update(page, new_text, summary)


if __name__ == "__main__":
    main()
