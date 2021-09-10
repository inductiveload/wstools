
import requests
import logging

from lxml import html


class HTDownloader():

    def __init__(self, htid, res, i):

        self.htid = htid
        self.i = i
        self.res = res

    def get(self):
        logging.debug("Download image: {}".format(self.i))
        return down_img(self.htid, self.i, self.res)


def get_hathi_section_element(hid):

    url = "https://babel.hathitrust.org/cgi/pt?id=" + hid

    req = requests.get(url)

    tree = html.fromstring(req.content)

    return tree.xpath('.//section[@id="section"]')[0]


def down_img(htid, i, res):

    rot = 0
    url = "https://babel.hathitrust.org/cgi/imgsrv/image?id={htid};seq={seq};size={res};rotation={rot}".format(
            htid=htid, seq=i, res=res, rot=rot)

    req = requests.get(url)

    content_type = req.headers['content-type']

    logging.debug("Page {}: {}".format(i, content_type))

    return req.content, content_type


def dl_images(htid, res=10000):

    section_elem = get_hathi_section_element(htid)

    maxseq = int(section_elem.attrib['data-total-seq'])

    logging.debug("Num pages: {}".format(maxseq))

    for i in range(1, maxseq + 1):
        yield htid, i, HTDownloader(htid, res, i)
