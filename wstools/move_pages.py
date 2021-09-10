#! /usr/bin/env python3

import argparse
import logging
import re


import pywikibot
import pywikibot.proofreadpage


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--from-index', required=True,
                        help='')
    parser.add_argument('-t', '--to-index',
                        help='The index to move to, or blank to use the same as --from-index')
    parser.add_argument('-o', '--offset', type=int, default=0,
                        help='Page shift from from to to index')
    parser.add_argument('-p', '--pages', nargs="+",
                        help='The pages to move')
    parser.add_argument('-n', '--dry-run', action="store_true",
                        help='Dry run')
    parser.add_argument('-l', '--lang', default="en",
                        help='Wikisource language subdomain')
    parser.add_argument('-r', '--redirect', action="store_true",
                        help='Add redirects')
    parser.add_argument('-s', '--summary',
                        help='The move edit summary (can use {to}, {from} and {offset})')
    parser.add_argument('-T', '--throttle', type=int,
                        help='Throttle in seconds')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.getLogger("pywiki").setLevel(pywikibot.logging.ERROR)

    pwbl = logging.getLogger("pywiki")
    pwbl.disabled = True

    if args.throttle is not None:
        pywikibot.config.put_throttle = args.throttle

    site = pywikibot.Site(args.lang, "wikisource")

    if args.to_index is None:
        args.to_index = args.from_index

    args.from_index = re.sub(r'^Index:', '', args.from_index, re.I)
    args.to_index = re.sub(r'^Index:', '', args.to_index, re.I)

    summary = ''
    if args.from_index == args.to_index:
        summary = f"Shifting pages by offset: {args.offset}"
    else:
        summary = f"Moving pages to new scan {args.to_index}"

        if args.offset:
            summary += f" with offset {args.offset}"

    if args.summary:
        summary += ': ' + args.summary.format(
            from_index=args.from_index,
            to_index=args.to_index,
            offset=args.offset
        )

    pages = []

    if len(args.pages) == 1:
        args.pages = args.pages[0].split(",")

    for p in args.pages:

        if len(p.split("-")) == 2:
            ps = p.split("-")
            pages += [i for i in range(int(ps[0]), int(ps[1]) + 1)]
        elif len(p.split("+")) == 2:
            ps = p.split("+")
            pages += [i for i in range(int(ps[0]), int(ps[0]) + int(ps[1]))]
        else:
            pages.append(int(p))

    pages.sort()

    if args.from_index == args.to_index and args.offset > 0:
        pages.reverse()

    print(pages)

    for i in pages:

        from_page_t = args.from_index.format(i)

        print(from_page_t)

        if from_page_t == args.from_index:
            # nothing changed, so this must be a "real index"
            from_page_t = "{}/{}".format(args.from_index, i)

        if not from_page_t.startswith("Page:"):
            from_page_t = "Page:" + from_page_t

        to_page_t = "Page:{}/{}".format(args.to_index, i + args.offset)

        from_pg = pywikibot.proofreadpage.ProofreadPage(site, from_page_t)

        logging.debug("Moving from {} -> {}".format(
                from_page_t, to_page_t))

        if not args.dry_run:

            try:
                from_pg.move(newtitle=to_page_t,
                             reason=summary,
                             noredirect=not args.redirect)
            except pywikibot.exceptions.NoPage:
                logging.info("Page does not exist: {}".format(from_page_t))
                pass
        else:
            logging.debug(summary)


if __name__ == "__main__":
    main()
