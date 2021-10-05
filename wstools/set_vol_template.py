#! /usr/bin/env python3

import argparse
import logging


import pywikibot
import pywikibot.proofreadpage

import mwparserfromhell


def set_vol_list(site, page, content, summary, dry_run):

    if not page.startswith("Index:"):
        page = "Index:" + page

    logging.debug(page)

    index = pywikibot.proofreadpage.IndexPage(site, page)

    s = index.get()

    wikicode = mwparserfromhell.parse(s)

    template = wikicode.filter_templates()[0]

    template.add("Volumes", content)

    logging.debug(wikicode)

    if not dry_run:
        index.put(wikicode, summary=summary)


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='Dry run')

    args = parser.parse_args()

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("pywiki").disabled = True

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    ws_site = pywikibot.Site("en", "wikisource")

    PAGES = [x for x in range(1, 24)]
    INDEX_FMT = "Index:Transactions NZ Institute Volume {}.djvu"
    TEMPLATE = "Transactions NZ Institute volumes"

    VOL_TEMPLATE = "{{{{{}}}}}".format(TEMPLATE)
    SUMMARY = "Adding volume template: [[Template:{}]]".format(TEMPLATE)

    PAGES = [INDEX_FMT.format(x) for x in PAGES]

    for p in PAGES:
        try:
            set_vol_list(ws_site, p, VOL_TEMPLATE, SUMMARY, args.dry_run)
        except pywikibot.exceptions.NoPageError:
            pass


if __name__ == "__main__":
    main()
