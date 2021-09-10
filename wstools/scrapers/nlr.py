"""
Scraper for National Library of Russia (Vivaldi)
"""
import requests
import logging

from lxml import html


class NLRDownloader():

    def __init__(self, htid, res, i):

        self.htid = htid
        self.i = i
        self.res = res

    def get(self):
        logging.debug("Download image: {}".format(self.i))
        return down_img(self.htid, self.i, self.res)


class NLRScraper():

    def scrape(bid):

        for i in range(1, maxseq + 1):
            yield bid, i, NLRDownloader(bid, i)
