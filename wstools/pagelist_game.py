#! /usr/bin/env python3

import argparse
import logging

import json

import requests
import requests_cache


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--index', required=True,
                        help='The index to pagelist')

    args = parser.parse_args()

    # requests_cache.install_cache('plg')

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    data = {
        "action": "parse",
        "format": "json",
        "formatversion": 2,
        "page": "Index:" + args.index,
        "prop": "wikitext",
        "contentformat": "application/json"
    }

    r = requests.get('https://en.wikisource.org/w/api.php', params=data)
    r.raise_for_status()

    idata = json.loads(r.json()['parse']['wikitext'])

    pagelist = idata['fields']['Pages']

    print(pagelist)


if __name__ == "__main__":
    main()