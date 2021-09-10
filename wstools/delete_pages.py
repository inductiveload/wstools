#! /usr/bin/env python3

import argparse
import logging

import pywikibot
import pywikibot.proofreadpage


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--index', required=True,
                        help='The index')
    parser.add_argument('-f', '--from-page', type=int, required=True,
                        help='First page')
    parser.add_argument('-t', '--to-page', type=int, required=True,
                        help='First page')
    parser.add_argument('-s', '--summary', required=True,
                        help='Deletion reason')
    parser.add_argument('-p', '--no_prompt', action='store_true',
                        help='No prompt to delete')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='DO not actually delete the page')
    parser.add_argument('-F', '--force-delete', action="store_true",
                        help='Delete even if the pages are not "not proofread"')
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    if args.from_page > args.to_page:
        raise ValueError("From > to!")

    site = pywikibot.Site("en", "wikisource")

    for pgnum in range(args.from_page, args.to_page + 1):

        page = pywikibot.proofreadpage.ProofreadPage(site, "Page:{}/{}".format(args.index, pgnum))

        if page.quality_level != page.NOT_PROOFREAD and not args.force_delete:
            print("Not deleting page {} with status {}".format(
                    page, page.quality_level))
            continue

        if not args.dry_run:
            page.delete(reason=args.summary, prompt=not args.no_prompt)
        else:
            print("Dry run: deleting page {}".format(page))


if __name__ == "__main__":
    main()
