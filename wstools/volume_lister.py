#! /usr/bin/env python3

import argparse
import logging

import requests
import requests_cache
import re

from lxml import html

class Volume():

    def __init__(self, volume, href, year=None):
        self.volume = volume
        self.href = href
        self.year = year

def get_vols(id):

    url = "https://catalog.hathitrust.org/Record/" + id

    r = requests.get(url)
    r.raise_for_status()

    tree = html.fromstring(r.content)

    volumes = []


    for e in tree.cssselect(".viewability-table tbody tr"):

        href = e.cssselect("td:first-child a")[0].attrib['href']
        volume = e.cssselect(".IndItem")[0].text

        match = re.search(r"\d{4}([/\-]\d{4})?", volume)

        if match:
            year = match.group(0).replace("/", "-")
        else:
            year = None

        match = re.search(r"v\.(\d+)", volume)
        volume = match.group(1)

        volumes.append(Volume(volume, href, year))

    return volumes

def format_list(vols):

    s = ""

    for v in vols:

        s += "* Volume {v}".format(v=v.volume)

        if v.year:
            s += " ({y})".format(y=v.year)

        s += " {{{{ext scan link|1={href}}}}}".format(href=v.href)

        s += "\n"
    return s

def format_tabs(vols, prefix):

    s = ""

    for v in vols:

        parts = [v.href]

        parts.append((prefix + "_" if prefix else "") + v.volume)

        if v.year:
            parts.append(v.year)

        s += "\t".join(parts)
        s += "\n"

    return s


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--id',
                        help='The source ID')
    parser.add_argument('-t', '--tabs', action='store_true',
                        help='Print with tabs')
    parser.add_argument('-p', '--vol_prefix',
                        help='Add a prefix to the tab volume name')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    requests_cache.install_cache('volume-lister')

    vols = get_vols(args.id)

    if args.tabs:
        ts = format_tabs(vols, args.vol_prefix)
    else:
        ts = format_list(vols)

    print(ts)

if __name__ == "__main__":
    main()