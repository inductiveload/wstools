#! /usr/bin/env python3

import mwparserfromhell
import pywikibot
from pywikibot import pagegenerators as PGens

import re
import sys

import logging
import argparse


class PageSuspector():

    def __init__(self, page):
        self.page = page

        logging.debug(page.text)

        wikicode = mwparserfromhell.parse(page.text)

        self.templates = wikicode.filter_templates()

        self.cat_whitelist = []

    def find_template(self, the_one):
        """
        Find the first template called 'the one'
        """

        try:
            return [x for x in self.templates if x.name.strip().lower() == the_one][0]
        except IndexError:
            return None

    def find_param(self, template_name, params):
        """
        Find the parameter named 'param' of the first template called 'template_name'
        Returns None if the template doesn't occur, or if it does, but the param does not
        """

        instance = self.find_template(template_name)

        # no template
        if not instance:
            return None

        for p in params:
            try:
                # print(p, instance.get(p))
                return instance.get(p).value.strip()
            except ValueError:
                continue

        # no parameter
        return None

    def find_date(self):

        date = self.find_param("book", ["date", "publication date"])

        if not date:
            date = self.find_param("information", ["date"])

        if not date:
            date = self.find_param("artwork", ["date"])

        return date

    def date_is_recent(self, date):
        """
        Return true if the date is "recent"
        """

        if re.search(r"\b19[5-9][0-9]\b", date):
            return True, "Date after 1949"

    def is_page_suspicious(self, page):

        cats = page.categories()

        for c in cats:
            c_title = c.title(with_ns=False).replace("_", " ")
            if c_title in self.cat_whitelist:
                return False, None

            if c_title.endswith('/reviewed'):
                return False, None

        date = self.find_date()

        if not date:
            return True, "No date"

        if self.date_is_recent(date):
            return True, "Date too recent: {}".format(date)

        # no other reason to be suspicious
        return False, None


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-p', '--print-every', default=1000, type=int,
                        help='print progress every nth file (good for logging when to restart)')
    parser.add_argument('-c', '--category',
                        help='The category to process')
    parser.add_argument('-s', '--start-at',
                        help='start at this file')
    parser.add_argument('-C', '--chunk', default=50, type=int,
                        help='API fetch chunk size (see phab:T253591)')
    parser.add_argument('-t', '--textfile',
                        help="Text file to read files from")

    parser.add_argument("-f", "--fff", help="a dummy argument to fool ipython", default="1")

    args = parser.parse_args()

    site = pywikibot.Site('commons', 'commons')

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("oauthlib.oauth1.rfc5849").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # >_<  sllllllowwwww see T253591
    # pywikibot.config.step = args.chunk
    # cat = pywikibot.Category(site, args.category)
    # gen = PGens.CategorizedPageGenerator(cat, start=args.start_at)

    negative_cats = [
            'PD US Government',
            'Public domain files with no author lifetime information',
            'Government of Canada publications',
            'PD US Census',
            'OGL-C',
            'PD Canada'
            'CC-PD-Mark'
            'National Institutes of Health images',
            'National Cancer Institute',
            'PD US Congress',
            'PD USDA',
        ]

    if args.textfile:
        gen = PGens.TextfilePageGenerator(args.textfile, site=site)
    else:

        if not args.category:
            raise RuntimeError("Need a category!")

        pywikibot.config.socket_timeout = (6.05, 600)

        gen = PGens.PetScanPageGenerator(
            [args.category],
            site=site,
            namespaces=[6],

            extra_options={
                'project': 'wikimedia',
                'language': 'commons',
                'negcats': negative_cats
            })

    i = 0

    for file in gen:

        # images, don't care
        if not (file.title().endswith(".pdf") or file.title().endswith(".djvu")):
            continue

        ps = PageSuspector(file)
        ps.cat_whitelist = negative_cats
        sus, why = ps.is_page_suspicious(file)

        if sus:
            logging.warning("{} is suspect: {}".format(file.title(), why))
        else:
            logging.debug("{} looks OK".format(file.title()))
            pass

        i += 1
        if (i % args.print_every) == 0:
            print('{:07d}\t{}'.format(i, file.title()))


def is_notebook():
    try:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True   # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False      # Probably standard Python interpreter


if __name__ == '__main__':

    if is_notebook():
        sys.argv[1:] = ARGS
    main()
