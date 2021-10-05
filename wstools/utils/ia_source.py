
import requests
import logging

from lxml import etree

import utils.pagelist

import utils.source


class IaSource(utils.source.Source):

    def __init__(self, id):
        self.id = self._normalise_id(id)
        self.filelist = None
        self.prefer_pdf = False

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

        if not self.filelist:
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

    def has_djvu(self):

        djvu_fileinfo = self._get_files_with_format("DjVu")
        return djvu_fileinfo is not None

    def get_jp2_zip(self):

        jp2_zip_fileinfo = self._get_files_with_format("Single Page Processed JP2 ZIP")

        if not jp2_zip_fileinfo:
            return None

        jp2_zip_name = jp2_zip_fileinfo[0].attrib['name']
        jp2_zip_size = int(jp2_zip_fileinfo[0].find('size').text)

        url = f'https://archive.org/download/{self.id}/{jp2_zip_name}'

        logging.debug(f'Downloading JP2 zip: {jp2_zip_name}')
        logging.debug(f' Size: {jp2_zip_size // (1024 * 1024)}MB')

        return utils.source.get_from_url(url, name=jp2_zip_name)

    def _get_scandata(self):

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

        return xml

    def get_pagelist(self):
        logging.debug("Getting IA pagelist for ID {}".format(self.id))

        xml = self._get_scandata()

        pages = xml.findall(".//{*}pageData/{*}page")

        pl = utils.pagelist.PageList()

        for pg in pages:

            addPage = pg.find(".{*}addToAccessFormats")

            if addPage is not None and addPage.text.lower() == "false":
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