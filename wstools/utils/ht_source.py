
import utils.pagelist as PL

import urllib
import json

import logging

import utils.source


module_logger = logging.getLogger('wstools.ht_source')


def normalise_id(htid):

    if "hdl.handle.net" in htid:
        return htid.split("/")[-1]
    elif "babel.hathitrust.org" in htid:
        u = urllib.parse("htid")
        u = urllib.parse_qs(u.query)
        return u['id']
    return htid


class HathiSource(utils.source.Source):

    def __init__(self, dapi, htid):
        self.htid = normalise_id(htid)
        self._metadata = None
        self.dapi = dapi

        self.direct_download = False

    def _meta(self):

        if self._metadata is None:
            r = self.dapi.getmeta(self.htid, json=True)
            self._metadata = json.loads(r)

        return self._metadata

    def get_num_pages(self):

        return int(self._meta()['htd:numpages'])

    def get_image_url(self):
        raise NotImplementedError("Hathi doesn't provide this")

    def get_image(self, seq):

        module_logger.debug("Getting image for sequence {}".format(seq))

        if not self.direct_download:
            data, image_type = self.dapi.get_image(self.htid, sequence=seq)
        else:
            res = 10000
            escaped_id = self.htid #replace('$', '_')
            url = 'https://babel.hathitrust.org/cgi/imgsrv/image?' \
                f'id={escaped_id};seq={seq};size={res};rotation=0'

            r = self.dapi.rsession.get(url)
            r.raise_for_status()

            data = r.content
            image_type = r.headers['content-type']
        return data, image_type

    def get_coord_ocr(self, seq):
        module_logger.debug("Getting OCR for sequence {}".format(seq))

        r = self.dapi.get_coord_ocr(self.htid, sequence=seq)

        # this chokes XML parsers
        r = r.replace("&shy;", "&#173;")

        # already in HOCR format
        return r

    def get_pagelist(self):

        pl = PL.PageList()

        # print(self._meta()['htd:seqmap'])

        for seq in self._meta()['htd:seqmap'][0]['htd:seq']:

            if seq['htd:pnum']:
                pn = seq['htd:pnum']
            else:
                pn = '–'

            pl.append(pn)

        return pl

    def get_id(self):
        return self.htid
