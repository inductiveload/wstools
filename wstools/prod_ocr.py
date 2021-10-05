#! /usr/bin/env python3

import argparse
import logging
import tqdm

import requests
import pywikibot
import pywikibot.proofreadpage

import utils.range_selection


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--index',
                        help='Index name')
    parser.add_argument('-p', '--pages', nargs='+',
                        help='the pages to fetch')

    args = parser.parse_args()

    site = pywikibot.Site('en', 'wikisource')

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    index = pywikibot.proofreadpage.IndexPage(site, 'Index:' + args.index)

    if args.pages:
        pages = utils.range_selection.get_range_selection(
            args.pages, index.num_pages)
    else:
        pages = range(1, index.num_pages + 1)

    for i in tqdm.tqdm(pages):
        w = 1024
        img_page = pywikibot.FilePage(site, 'File:' + args.index)
        img_url = img_page.get_file_url(url_param=f'page{i}-{w}px')

        url = "https://ocr.wmcloud.org/api.php"

        params = {
            'engine': 'tesseract',
            'langs[]': 'en',
            'image': img_url,
            'uselang': 'en'
        }

        requests.get(url, data=params)
        logging.debug(params)


if __name__ == "__main__":
    main()
