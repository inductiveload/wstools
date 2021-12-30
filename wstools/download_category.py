#! /usr/bin/env python3

import argparse
import logging

import pywikibot
import os
import fnmatch
import tqdm
import re


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-c', '--category',
                        help='The category')
    parser.add_argument('-f', '--file',
                        help='A list of filenames in a text file')
    parser.add_argument('-g', '--glob',
                        help='A glob pattern')
    parser.add_argument('-o', '--outdir', required=True,
                        help='Output dir')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    os.makedirs(args.outdir, exist_ok=True)

    site = pywikibot.Site('commons', 'commons')
    # site = pywikibot.Site('en', 'wikisource')

    if args.category:
        category = pywikibot.Category(site, args.category)
        files = [file for file in category.articles(namespaces=['File'])]
    elif args.file:
        files = []
        with open(args.file, 'r') as inf:
            for line in inf:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('#'):
                    continue

                fn = 'File:' + re.sub('^(Image|File):', '', line, re.I)
                files.append(pywikibot.FilePage(site, fn))
    else:
        raise ValueError('No source')

    for page in tqdm.tqdm(files):

        title = page.title(with_ns=False)

        if args.glob:
            if not fnmatch.fnmatch(title, args.glob):
                logging.debug(f'Skipping non-match {title}')
                continue

        ofname = os.path.join(args.outdir, title)
        page.download(ofname)


if __name__ == "__main__":
    main()
