
import requests
import logging

from lxml import etree
import re
import os

import utils.pagelist

import utils.source

import internetarchive

class IaSource(utils.source.Source):

    def __init__(self, id):
        self.id = self._normalise_id(id)
        self.filelist = None
        self.prefer_pdf = False

        self._scandata_cache = None

        self.item = internetarchive.get_item(self.id)

    def can_download_file(self):
        return True

    def _get_download_url(self, filename):

        url = "https://archive.org/download/{iaid}/{fn}".format(
                    iaid=self.id, fn=filename)
        return url

    def _get_filelist(self):

        if self.filelist is not None:
            return self.filelist

        logging.debug("Getting IA file list for {}".format(self.id))

        url = self._get_download_url("{iaid}_files.xml".format(iaid=self.id))

        r = requests.get(url)

        # print(r.content)

        tree = etree.fromstring(r.content)

        self.filelist = tree
        return tree

    def _get_files_with_format(self, fmt):

        def with_format(files, format):
            return [x for x in files if x.find("./format").text.lower() == format.lower()]

        filelist = self._get_filelist()

        files = filelist.findall(".//file")

        # print([x.find("./format").text for x in files])

        files = with_format(files, fmt)

        return files

    def _get_best_file(self):

        djvus = self._get_files_with_format("DjVu")
        pdfs = self._get_files_with_format("Text PDF")

        if pdfs and (not djvus or self.prefer_pdf):
            return pdfs[0].attrib['name']

        if djvus:
            return djvus[0].attrib['name']

        return None

    def get_file_url(self):

        logging.debug(f"Getting IA source URL for ID {self.id}")

        filename = self._get_best_file()

        if filename is not None:
            url = "https://archive.org/download/{iaid}/{fn}".format(
                iaid=self.id, fn=filename)
        else:
            url = None

        return url

    def _get_file_url(self, fmt):
        fileinfo = self._get_files_with_format(fmt)

        if fileinfo is None or len(fileinfo) == 0:
            return None, None

        name = fileinfo[0].attrib['name']
        url = f'https://archive.org/download/{self.id}/{name}'

        return url, fileinfo

    def get_file_url(self, fmt):
        url, _ = self._get_file_url(fmt)
        return url

    def get_file(self, fmt):
        url, fileinfo = self._get_file_url(fmt)

        size = int(fileinfo[0].find('size').text)
        name = fileinfo[0].attrib['name']

        logging.debug(f'Downloading {fmt}: {url}')
        logging.debug(f' Size: {size // (1024 * 1024)}MB')

        return utils.source.get_from_url(url, name=name, cache_key='ia-' + name)

    def get_jp2_zip(self):
        return self.get_file("Single Page Processed JP2 ZIP")

    def get_jp2_zip_name(self):
        _, fileinfo = self._get_file_url("Single Page Processed JP2 ZIP")
        return fileinfo[0].attrib['name']

    def has_djvu(self):

        djvu_fileinfo = self._get_files_with_format("DjVu")
        return djvu_fileinfo is not None and len(djvu_fileinfo) > 0

    def get_djvu(self):
        return self.get_file("DjVu")

    def get_jp2_list(self):
        urls = []

        zip_name = self.get_jp2_zip_name()
        zip_head, _ = os.path.splitext(zip_name)
        image_prefix = re.sub(r'_jp2$', '', zip_head)

        indexes = self.get_all_output_file_indexes()

        # this is a hack: can we get it from the API?
        for index in indexes:
            url = f'https://archive.org/download/{self.id}/' + \
                f'{zip_name}/{zip_head}%2F{image_prefix}_{index:04}.jp2'

            urls.append({
                'url': url,
                'index': index,
                'ext': '.jp2'
            })
        return urls

    def get_jpg_list(self):

        # Just defer to the JP2 function
        urls = self.get_jp2_list()

        def transform(jp2_url_item):
            newurl = jp2_url_item.copy()
            newurl['url'] += f'&ext=jpg'
            newurl['ext'] = '.jpg'
            return newurl

        jpg_urls = [transform(url) for url in urls]

        return jpg_urls


    def get_file_indexes_not_in_output(self):

        sd = self._get_scandata()

        indexes = []

        for page in sd.findall('.//{*}pageData/{*}page'):
            if not self.page_in_accessformats(page):
                index = int(page.attrib['leafNum'])
                indexes.append(index)

        return indexes

    def get_all_output_file_indexes(self):

        sd = self._get_scandata()

        indexes = []

        for page in sd.findall('.//{*}pageData/{*}page'):
            if self.page_in_accessformats(page):
                index = int(page.attrib['leafNum'])
                indexes.append(index)

        return indexes

    def _get_scandata(self):

        if self._scandata_cache is not None:
            return self._scandata_cache

        scandata_name = self._get_files_with_format("Scandata")

        if scandata_name:
            scandata_name = scandata_name[0].attrib['name']
        else:

            scandata_name = self._get_files_with_format("Scribe Scandata ZIP")

            if scandata_name:
                scandata_name = scandata_name[0].attrib['name'] + "/scandata.xml"

        logging.debug("Scan data found: {}".format(scandata_name))
        sdurl = self._get_download_url(scandata_name)

        r = requests.get(sdurl)

        r.raise_for_status()
        # print(r.content)

        xml = etree.fromstring(r.content)

        self._scandata_cache = xml

        return self._scandata_cache

    @staticmethod
    def page_in_accessformats(page):
        add_page = page.find(".{*}addToAccessFormats")

        if add_page is not None and add_page.text.lower() == "false":
            return False

        return True

    def get_pagelist(self):
        logging.debug("Getting IA pagelist for ID {}".format(self.id))

        xml = self._get_scandata()

        pages = xml.findall(".//{*}pageData/{*}page")

        pl = utils.pagelist.PageList()

        for pg in pages:
            if not self.page_in_accessformats(pg):
                continue

            pageTypeE = pg.find(".{*}pageType")
            pn = ""
            if pageTypeE is not None:

                if pageTypeE.text in ["Title", "Title Page"]:
                    pn = "Title"
                elif pageTypeE.text in ["Cover"]:
                    pn = "Cover"

            if not pn:

                pageNumberE = pg.find(".{*}pageNumber")

                if pageNumberE is None or pageNumberE.text is None:
                    pn = "–"
                else:
                    pn = pageNumberE.text

            pl.append(pn)

        return pl

    @staticmethod
    def _normalise_id(id):

        if id.startswith("http"):

            return id.split("/")[-1]

        return id

    def get_id(self):
        return self.id