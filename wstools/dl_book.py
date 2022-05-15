#! /usr/bin/env python3

import argparse
import logging
import urllib
import dotenv
import os

import dl_hathi
import dl_ia

import utils.ht_source
import utils.ht_api
import utils.ia_source
import utils.url_source

import urllib.parse

class DlDef():
    def __init__(self, src, id, filename):
        self.src = src.lower()
        self.id = id
        self.skip_existing = False
        self.use_proxy = False
        self.hathi_direct = False
        self.exclude_pages = []
        self.include_pages = []
        self.force_dl = False
        self.regenerate = False

        self.source = self._get_source()

        self.filename = filename

        if not self.filename:
            self.filename = self.get_id().replace('/', '_')

    def _get_source(self):
        if self.src == 'ia':
            self.source = utils.ia_source.IaSource(self.id)
        elif self.src == 'ht':
            dapi = utils.ht_api.DataAPI(client_key=None, client_secret=None,
                                        proxies=self.use_proxy, secure=True)
            self.source = utils.ht_source.HathiSource(dapi, self.id)
        elif self.src == 'url':
            self.source = utils.url_source.UrlSource(self.id)

        return self.source

    def get_id(self):
        return self.source.get_id()

    def get_pagelist(self):
        source = self.source
        if source:
            pagelist = source.get_pagelist()
            print( pagelist )
            if pagelist:
                pagelist.clean_up()
            return pagelist
        return None

    def do_download(self, dl_dir):
        source = self.source

        if not os.path.exists(dl_dir):
            os.makedirs(dl_dir, exist_ok=True)

        if self.src == 'ht':
            return dl_hathi.download(self.hathi_direct, self.get_id(), dl_dir,
                                    skip_existing=self.skip_existing,
                                    proxy=self.use_proxy,
                                    include_pages=self.include_pages,
                                    exclude_pages=self.exclude_pages)
        elif self.src == 'ia':
            return dl_ia.download(self.source, dl_dir,
                                skip_existing=self.skip_existing,
                                skip_djvu=not self.force_dl,
                                get_images=self.regenerate,
                                include_pages=self.include_pages,
                                exclude_pages=self.exclude_pages)
        elif self.src == 'url':
            dest_fn = os.path.join(dl_dir, source.get_file_name())

            if self.skip_existing and os.path.exists(dest_fn):
                return dest_fn

            # buffer = io.BytesIO()
            fo = source.download(proxy=self.use_proxy)

            if fo is not None:

                with open(dest_fn, 'wb') as dest_fo:
                    fo.seek(0)
                    dest_fo.write(fo.read())
                return dest_fn
            return None
        else:
            raise NotImplementedError


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--id',
                        help='The source identifier')
    parser.add_argument('-s', '--src',
                        help='The source key (e.g. ia for Internet Archive)')
    parser.add_argument('-o', '--outdir',
                        help='The output dir')

    args = parser.parse_args()

    dotenv.load_dotenv()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)


if __name__ == "__main__":
    main()
