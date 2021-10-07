#! /usr/bin/env python3

import argparse
import logging

from xlsx2csv import Xlsx2csv
from io import StringIO
import csv
import os
import dotenv
import re
import itertools
import io
import urllib.parse
import time

import utils.pagelist
import utils.source
import utils.ia_source
import utils.ht_source
import utils.ht_api
import utils.commonsutils
import utils.string_utils
import utils.ia_upload
import utils.phab_tasks
import utils.update_bar
import utils.range_selection

import requests
# import requests_cache


import pywikibot
import pywikibot.proofreadpage
import mwparserfromhell

# for Toolforge uploading
import paramiko
import scp

import subprocess


WS_LOCAL = {
    'en': {
        'no_commons': {
            'title': 'Do not move to Commons',
            'until': 'until',
            'reason': 'why'
        }
    }
}


def image_exists_as_image(filepage):
    try:
        filepage.get_file_url()
        has_image_info = filepage.exists()
    except pywikibot.exceptions.PageRelatedError:
        has_image_info = False

    return has_image_info


def handle_upload_warning(warnings):

    logging.error(warnings)

    for w in warnings:
        if w.code not in ['was-deleted', 'exists-normalized', 'page-exists']:
            return False

    return True


class UploadHandler():

    def upload(self, name, file, desc):
        raise NotImplementedError


class StandardWikiUpload(UploadHandler):

    def __init__(self, site):
        self.site = site
        self.write_filepage_on_failure = True
        self.simulate_stash_failure = False
        self.chunk_size = 1024 * 1024

    def exists(self, name):

        fp = pywikibot.FilePage(self.site, "File:" + name)
        return fp.exists()

    def upload(self, name, file_url, desc):

        filepage = pywikibot.FilePage(self.site, "File:" + name)

        try:
            if self.simulate_stash_failure:
                logging.debug(f"Simulating stash failure at {self.site}")
                raise pywikibot.exceptions.APIError('stashfailed', '')

            if file_url.startswith("http"):
                self.site.upload(filepage, source_url=file_url,
                                 comment=desc,
                                 report_success=False,
                                 ignore_warnings=handle_upload_warning)
            else:
                self.site.upload(filepage, source_filename=file_url,
                                 comment=desc, report_success=False,
                                 ignore_warnings=handle_upload_warning,
                                 chunk_size=self.chunk_size,
                                 asynchronous=True)
        except pywikibot.exceptions.Error as e:

            logging.info(f'WMF upload failed with {e}')

            if self.write_filepage_on_failure:
                logging.debug("Writing description without file present")

                filepage.put(
                    desc,
                    summary="File description for failed upload, pending server-side upload.",
                    ignore_warnings=handle_write_filepage_warning,
                )
            return False
        return True


class UploadToIA(UploadHandler):

    def __init__(self):
        self.ssu_url = None

    def upload(self, name, file_url, desc, file_metadata):
        self.ssu_url = None
        logging.debug(f'Attempting IA upload of {file_url}')
        ia_id, ia_file = utils.ia_upload.upload_file(
            file_url,
            name,
            file_metadata.get('title'),
            volume=file_metadata.get('volume'),
            author=file_metadata.get('author'),
            editor=file_metadata.get('editor'),
            date=file_metadata.get('year'),
            src_url=None
        )

        self.ssu_url = f'https://archive.org/download/{ia_id}/{ia_file}'
        logging.debug(f'Uploading to IA complete: {ia_id}')


class UploadToSshHost(UploadHandler):

    def __init__(self, ssh, path):
        self.ssh = ssh
        self.path = path

    def upload(self, name, file_url, desc):
        logging.debug('Uploading to host:' + self.ssh._remote_hostname)

        tail_root, _ = os.path.splitext(name)
        dest_file = os.path.join(self.path, name)
        dest_desc_file = os.path.join(self.path, tail_root + '.txt')

        with utils.update_bar.ParamikoTqdmWrapper(
                unit='B', unit_scale=True) as pbar:

            with scp.SCPClient(
                    self.ssh.get_transport(), progress=pbar.view_bar) as scp_client:

                if file_url.startswith('http'):
                    dl_buffer = utils.source.get_from_url(file_url)
                    scp_client.putfo(dl_buffer, dest_file)
                else:
                    scp_client.put(file_url, dest_file)

                desc_fo = io.BytesIO(desc.encode('utf8'))
                scp_client.putfo(desc_fo, dest_desc_file)

        return [
            dest_file,
            dest_desc_file
        ]


def wait_for_file_to_exist(filepage, max_delay, delay_step=5):

    delay = 0
    while delay <= max_delay:
        if image_exists_as_image(filepage):
            return True
        time.sleep(delay)
        delay += delay_step

    return False


class UploadViaToolforgeSsh(UploadHandler):

    def __init__(self, site):
        self.site = site

        self.host = "login.tools.wmflabs.org"
        self.path = os.getenv('TOOLFORGE_STORAGE_PATH')
        self.username = os.getenv('TOOLFORGE_SSH_USERNAME')
        self.keyfile = os.getenv('TOOLFORGE_SSH_KEYFILE')
        self.external_url = os.getenv('TOOLFORGE_FILE_STORE_URL')

    def upload(self, name, file_url, desc):
        logging.debug(f'Uploading via Toolforge to {self.site}')

        ssh = paramiko.SSHClient()
        # hack, but Paramiko doesn't provide this
        ssh._remote_hostname = self.host
        ssh.load_system_host_keys()
        ssh.connect(self.host, username=self.username, key_filename=self.keyfile)

        ssh_uploader = UploadToSshHost(ssh, self.path)
        upped_files = ssh_uploader.upload(name, file_url, desc)

        ext_url = self.external_url + urllib.parse.quote(name)

        filepage = pywikibot.FilePage(self.site, 'File:' + name)

        #  now that the file is uploaded to TF, copy-upload to the site
        try:
            logging.debug(f'Copy-uploading: {ext_url} -> {self.site}')
            self.site.upload(filepage, source_url=ext_url,
                             comment=desc,
                             report_success=False,
                             ignore_warnings=handle_upload_warning)
        except pywikibot.exceptions.APIError as e:
            # the upload _seems_ to have failed, but it could have worked and
            # just timed us out. So poll for a bit.
            print(e.__dict__)
            if e.code == '':
                if not wait_for_file_to_exist(filepage, 60):
                    # file never appeared :-s
                    raise
            else:
                # some other error happened
                raise

        # now delete the files (if exception above, leave them in place)
        with ssh.open_sftp() as sftp:
            for file in upped_files:
                logging.debug(f'Deleting: {file}')

                try:
                    sftp.remove(file)
                except FileNotFoundError:
                    # should not happen, but maybe someone SSHed in and messed
                    # with it or something
                    pass


def parse_header_row(hr):

    mapping = {}

    for i, col in enumerate(hr):
        mapping[col.lower()] = i

    return mapping


def combine_linked(authors):

    links = ["[[{}|]]".format(a) for a in authors if a]

    return utils.string_utils.combine_list(links)


def combine_authors_linked(authors):

    links = ["[[Author:{}|]]".format(a) for a in authors if a]

    return utils.string_utils.combine_list(links)


def get_sortkey(s):
    titlewords = s.split()
    if titlewords[0].lower() in ["the", "a", "an"]:
        key = " ".join(titlewords[1:]) + ", " + titlewords[0]
    else:
        key = ""
    return key


FIELD_MAP = {
    'en': {
        'params': {
            'type': 'Type',
            'title': 'Title',
            'lang': 'Language',
            'volume': 'Volume',
            'author': 'Author',
            'translator': 'Translator',
            'editor': 'Editor',
            'illustrator': 'Illustrator',
            'school': 'School',
            'publisher': 'Publisher',
            'printer': 'None',
            'city': 'Address',
            'year': 'Year',
            'key': 'Key',
            'isbn': 'ISBN',
            'oclc': 'OCLC',
            'lccn': 'LCCN',
            'bnf_ark': 'BNF_ARK',
            'arc': 'ARC',
            'source': 'Source',
            'image': 'Image',
            'progress': 'Progress',
            'pages': 'Pages',
            'volumes': 'Volumes',
            'remarks': 'Remarks',
            'valid_date': 'Validation date',
            'transclusion': 'Transclusion',
            'wikidata': 'Wikidata',
            'css': 'Css',
            'header': 'Header',
            'footer': 'Footer',
            'width': 'Width',
        },
        'formats': {
            'title': "''[[{}]]''"
        },
        'default_progress': 'X',
        'default_transclusion': 'no',
        'default_type': 'book',
        'field_order': [
            'type', 'title', 'lang', 'volume', 'author', 'editor',
            'translator', 'illustrator', 'publisher',  # 'printer',
            'city', 'year', 'key', 'isbn', 'oclc', 'lccn', 'bnk_ark',
            'arc', 'source', 'image',
            'progress', 'transclusion', 'valid_date', 'pages',
            'remarks', 'wikidata', 'volumes',
            'width', 'css', 'header', 'footer'
        ]
    },
    'es': {
        'params': {
            'title': 'Titulo',
            'subtitle': 'Subtitulo',
            'lang': 'Idioma',
            'volume': 'Volumen',
            'author': 'Autor',
            'translator': 'Traductor',
            'editor': 'Editor',
            'illustrator': 'Ilustrador',
            'publisher': 'Editorial',
            'printer': 'Imprenta',
            'city': 'Lugar',
            'file_source': 'Fuente',
            'year': 'Ano',
            'key': 'Key',
            'image': 'Imagen',
            'progress': 'Progreso',
            'pages': 'Paginas',
            'volumes': 'Serie',
            'remarks': 'Notas',
            'wikidata': 'Wikidata',
            'country': 'derechos',
            'header': 'Header',
            'footer': 'Footer',
        },
        'default_progress': 'C',
        'field_order': [
            'title', 'subtitle', 'lang', 'volume', 'author', 'editor',
            'translator', 'publisher', 'printer', 'city', 'illustrator',
            'year', 'country', 'file_source', 'image',
            'progress', 'pages', 'remarks', 'wikidata', 'volumes',
            'header', 'footer'
        ]
    },
}


def make_index_content(r, typ, phab_id=None, lang='en'):

    vlist = r.get('vollist') or ""

    title = r.get('mainspace') or r.get('title')
    subtitle = r.get('subtitle') or ""

    volume = ''
    if r.get('volume'):

        subpage = r.get('subpage')
        if not subpage:
            subpage = "Volume " + r.get('volume')

        subpage_disp = r.get('subpage_disp') or subpage

        volume = f'[[{title}/{subpage}|{subpage_disp}]]'

        if r.get('vol_detail'):
            volume += " ({})".format(r.get('vol_detail'))

    year = r.get('year') or (r.get('date') or "")
    key = get_sortkey(title)

    remarks = ''
    if phab_id:
        remarks = f'Pending server-side upload: [[phab:T{phab_id}]]'

    fmap = FIELD_MAP[lang]

    template = mwparserfromhell.nodes.Template(
        ":MediaWiki:Proofreadpage_index_template"
    )

    for field in fmap['field_order']:

        value = None
        if field == 'type':
            value = 'book'
        elif field == 'source':
            value = typ
        elif field == 'lang':
            value = r.get('language') or ""
        elif field == 'title':
            value = title
        elif field == 'subtitle':
            value = subtitle
        elif field == 'volume':
            value = volume
        elif field == 'author':
            value = r.get('ws_author') or ""
        elif field == 'editor':
            value = r.get('ws_editor') or ""
        elif field == 'translator':
            value = r.get('ws_translator') or ""
        elif field == 'illustrator':
            value = r.get('ws_illustrator') or ""
        elif field == 'publisher':
            value = r.get('publisher') or ""
        elif field == 'printer':
            value = r.get('printer') or ""
        elif field == 'year':
            value = year
        elif field == 'city':
            value = r.get('city') or ""
        elif field == 'country':
            value = r.get('country') or ""
        elif field == 'file_source':
            value = r.get('file_source')
        elif field == 'image':
            value = r.get('img_pg') or ""
        elif field == 'progress':
            value = r.get('progress') or fmap['default_progress']
        elif field == 'pages':
            value = r.get('pagelist') or ""
        elif field == 'remarks':
            value = remarks
        elif field == 'wikidata':
            value = r.get('wikidata') or ""
        elif field == 'volumes':
            value = vlist
        elif field == 'transclusion':
            value = r.get('transclusion') or fmap['default_transclusion']
        elif field == 'valid_date':
            value = r.get('valid_date') or ""
        elif field == 'footer':
            value = r.get('footer') or ""
        elif field == 'css':
            value = r.get('css') or ""
        elif field == 'header':
            value = r.get('header') or ""
        elif field == 'footer':
            value = r.get('footer') or ""

        elif field == 'oclc':
            value = r.get('OCLC') or ""
        elif field == 'issn':
            value = r.get('ISSN') or ""
        elif field == 'lccn':
            value = r.get('LCCN') or ""
        elif field == 'bnf_ark':
            value = r.get('BNF_ARK') or ""
        elif field == 'arc':
            value = r.get('ARC') or ""
        elif field == 'key':
            value = key

        if value is not None:
            param = fmap['params'][field]

            # use a formatter if there is one
            if 'formats' in fmap and field in fmap['formats']:
                value = fmap['formats'][field].format(value.strip())
            else:
                value = value.strip()

            template.add(param, value + '\n')

    return re.sub(r'\n\n+', '\n', str(template))


def make_description(r, typ):

    lic = r.get('license').replace("—", "-").replace("–", "-")

    if lic.lower() == "pd-old-expired-auto":
        lic == "PD-old-auto-expired"

    if lic == "PD-old-auto-expired" and 'deathyear' in r:
        lic += "|deathyear=" + r.get('deathyear')

    top_content = ''
    local = r.get_bool('to_ws', False)

    if local:
        wsl = WS_LOCAL['en']
        dnmtc = mwparserfromhell.nodes.template.Template(wsl['no_commons']['title'])

        if r.get('no_commons_until'):
            dnmtc.add(wsl['no_commons']['until'], r.get('no_commons_until'))

        if r.get('no_commons_reason'):
            dnmtc.add(wsl['no_commons']['reason'], r.get('no_commons_reason'))
        top_content = str(dnmtc)

    if local:
        license = f'{{{{{lic}}}}}'
    else:
        license = f'{{{{PD-scan|{lic}}}}}'

    if r.get('source') == "ia":
        source = "{{{{IA|{iaid}}}}}".format(iaid=r.get('id'))
    elif r.get('source') == 'ht':
        source = "{{{{HathiTrust|{htid}|book}}}}".format(htid=r.get('id'))
    elif r.get('source') == "url":
        source = r.get('id')
    else:
        raise("Unknown source: {}".format(r.get('source')))

    langname = utils.commonsutils.lang_cat_name(r.get('language'))

    cats = []

    if not local:
        if typ == "djvu":
            cats.append(f"DjVu files in {langname}")
        else:
            cats.append(f"PDF files in {langname}")

    if r.get('commonscats'):
        cats += r.get('commonscats').split("/")

    date = r.get('date') or ""
    year = r.get('year') or date

    if not date and year:
        date = year

    cats = "\n".join([f"[[Category:{x}]]" for x in cats])

    if r.get('vol_disp'):
        volume = r.get('vol_disp')
    elif r.get('volume'):
        volume = r.get('volume')
    else:
        volume = ""

    if r.get('vol_detail'):
        volume += f' ({r.get("vol_detail")})'

    s = """
== {{{{int:filedesc}}}} ==
{top_content}
{{{{Book
| Author       = {author}
| Editor       = {editor}
| Translator   = {translator}
| Illustrator  =
| Title        = {title}
| Subtitle     = {subtitle}
| Series title =
| Volume       = {volume}
| Edition      =
| Publisher    = {publisher}
| Printer      = {printer}
| Date         = {date}
| City         = {city}
| Language     = {{{{language|{language}}}}}
| Description  =
| Source       = {source}
| Image        = {{{{PAGENAME}}}}
| Image page   = {img_page}
| Permission   =
| Other versions =
| Wikisource   = s:en:Index:{{{{PAGENAME}}}}
| Homecat      =
| Wikidata     =
| OCLC         = {oclc}
| ISBN         = {isbn}
| LCCN         = {lccn}
}}}}

== {{{{int:license-header}}}} ==
{license}

{cats}
""".format(
        license=license,
        top_content=top_content,
        author=r.get('commons_author') or "",
        editor=r.get('commons_editor') or "",
        translator=r.get('commons_translator') or "",
        title=r.get('title') or "",
        subtitle=r.get('subtitle') or "",
        volume=volume,
        publisher=r.get('publisher') or "",
        printer=r.get('printer') or "",
        city=r.get('city') or "",
        date=date,
        language=r.get('language'),
        source=source,
        img_page=r.get('img_pg') or "",
        cats=cats,
        oclc=r.get('oclc') or "",
        isbn=r.get('isbn') or "",
        lccn=r.get('lccn') or "",
        )

    return s


def get_wd_site_author(repo, wdqid):

    item = pywikibot.ItemPage(repo, wdqid)

    # this will throw if there's no enWS page, but we're SOL at that point
    return item.getSitelink("enwikisource")


def get_commons_creator(wdqid):

    if not re.match(r'Q[0-9]+', wdqid):
        logging.debug("Not a Wikidata ID: {}".format(wdqid))
        return wdqid

    return "{{{{creator|wikidata={}}}}}".format(wdqid)


def get_wd_site_info(site, r, key):
    """
    Note, this assumes the parts are ALL wikidata IDs or ALL author page names
    """
    parts = []
    if r.get(key):
        parts = r.get(key).split("/")

    if not parts or not re.match("Q[0-9]+", r[key]):
        r.set('commons_' + key, utils.string_utils.combine_list(parts))
        r.set('ws_' + key, combine_authors_linked(parts))

    else:
        repo = site.data_repository()

        r.set('commons_' + key, "\n".join(["{{{{creator|wikidata={}}}}}".format(a) for a in parts]))
        r.set('ws_' + key, combine_linked([get_wd_site_author(repo, a) for a in parts]))


def handle_warning(warnings):

    logging.error(warnings)

    for w in warnings:
        if w.code not in ['was-deleted', 'exists-normalized']:
            return False

    return True


def handle_write_filepage_warning(warnings):

    logging.error(warnings)

    # if len(warnings) == 1:

    #     if warnings[0].code == 'exists-normalized':
    #         return True

    # continue
    return False


def split_any(txt, seps):
    default_sep = seps[0]

    # we skip seps[0] because that's the default separator
    for sep in seps[1:]:
        txt = txt.replace(sep, default_sep)
    return [i.strip() for i in txt.split(default_sep)]


def find_file(r, in_dir):

    candidate_fns = []
    candidate_exts = ['.djvu', '.pdf']

    if r.get('id'):
        candidate_fns.append(r.get('id'))

    if r.get('filename'):
        candidate_fns.append(r.get('filename'))

    for n in candidate_fns:

        print(n)
        _, ext = os.path.splitext(n)
        if ext not in candidate_exts:
            exts = candidate_exts
        else:
            exts = ['']

        for e in exts:
            try_file = os.path.join(in_dir, n + e)
            if os.path.isfile(try_file):
                return try_file

    return None


def handle_row(r, args):

    if r.get_bool('skip', False):
        logging.debug("Skipping row")
        return False

    if r.get('source') == "ia":
        source = utils.ia_source.IaSource(r.get('id'))
        if r.get('prefer_pdf'):
            source.prefer_pdf = True
    elif r.get('source') == "ht":
        dapi = utils.ht_api.DataAPI(proxies=args.proxy)
        source = utils.ht_source.HathiSource(dapi, r.get('id'))
    else:
        source = None

    if source is not None:
        # normalise the ID
        r.set('id', source.get_id())

    file_url = None

    if r.get('file'):

        # use local files if given
        file_url = r.get('file')

        if os.path.isdir(file_url):
            # path exists, but it's just a dir, so magically guess
            file_url = find_file(r, file_url)

        elif args.file_dir and not os.path.isabs(file_url):
            file_url = os.path.join(args.file_dir, file_url)

        if not file_url:
            raise RuntimeError(f'Cannot find file: {r.get("file")}')

        logging.debug("Local file size {} MB: {}".format(
            os.path.getsize(file_url) // (1024 * 1024), file_url))
    else:

        # first see if we have a handy local file
        if args.file_dir:
            candidate_fns = itertools.product(
                [
                    utils.source.sanitise_id(r.get('id')),
                    r.get('filename')
                ],
                ['.djvu', 'pdf']
            )

            for root, ext in candidate_fns:
                fn = os.path.join(args.file_dir, root + ext)
                if os.path.isfile(fn):
                    file_url = fn
                    break

        if not file_url:
            if source.can_download_file():
                file_url = source.get_file_url()
            else:
                logging.error('No local file and the source cannot provide one')

    logging.debug("File source: {}".format(file_url))

    root, ext = os.path.splitext(file_url)

    dl_file = None
    if r.get_bool('dl', False) and file_url.startswith("http"):
        # actually download the file
        logging.debug("Downloading file: {}".format(file_url))

        req = requests.get(file_url)
        req.raise_for_status()

        dl_file = "/tmp/dlfile" + ext

        with open(dl_file, "wb") as tf:
            tf.write(req.content)
        logging.debug("Wrote file to: {}".format(dl_file))

        file_url = dl_file

    if dl_file and r.get('rem_pg'):
        pages = split_any(r.get('rem_pg'), [" ", ","])

        print(pages)
        pages = [int(x) for x in pages]
        pages.sort(reverse=True)

        for p in pages:
            if ext == ".djvu":
                cmd = ["djvm", "-d", dl_file, str(p)]
                logging.debug("Deleting page {}".format(p))
                subprocess.call(cmd)

    if not r.get('pagelist'):
        if source is not None:
            try:
                pagelist = source.get_pagelist()
                pagelist.clean_up()
            except:
                logging.error("Failed to get pagelist")
                raise
                pagelist = None

        else:
            pagelist = None

        if not r.get("img_pg"):
            r.set('img_pg', '')

        if pagelist is not None:

            page_offset = 0
            if r.get('pg_offset'):
                page_offset = int(r.get('pg_offset'))

            if not r.get('img_pg') and pagelist.title_index is not None:
                r.set('img_pg', str(pagelist.title_index - page_offset))

            r.set('pagelist', pagelist.to_pagelist_tag(page_offset))
        else:
            r.set('pagelist', '<pagelist/>')

    # if not r.get('oclc'):
    #     r.set('oclc', source.get_oclc())

    if not r.get('year'):
        r.set('year', r.get('date'))

    if not r.get('filename').lower().endswith(ext.lower()):
        r.set('filename', r.get('filename') + ext)

    ws_site = pywikibot.Site(args.ws_language, "wikisource")

    upload_to_ws = r.get_bool('to_ws', False)

    if upload_to_ws:
        upload_site = ws_site
    else:
        upload_site = pywikibot.Site("commons", "commons")

    get_wd_site_info(ws_site, r, 'author')
    get_wd_site_info(ws_site, r, 'editor')
    get_wd_site_info(ws_site, r, 'translator')

    filetype = ext[1:]
    desc = make_description(r, filetype)
    print(desc)

    # filter out nasties in the filename
    cms_fn = r.get('filename').replace("—", "-").replace("–", "-")
    filepage = pywikibot.FilePage(upload_site, "File:" + cms_fn)

    logging.debug(filepage)

    do_upload = True

    try:
        filepage.get_file_url()
        has_image_info = filepage.exists()
    except pywikibot.exceptions.PageRelatedError:
        has_image_info = False

    if has_image_info and not args.skip_upload:
        logging.warning("File page exists: {}".format(cms_fn))

        if args.exist_action == 'skip':
            logging.info("Skipping file upload")
            do_upload = False

        if args.exist_action == 'update':
            filepage.text = desc
            summary = "Updating description from batch upload data"
            if not args.dry_run:
                filepage.save(
                    summary=summary,
                    ignore_warnings=handle_write_filepage_warning
                )
            else:
                logging.info(f"Dry run: skipped description update, would have saved with message '{summary}'")

            do_upload = False

    phab_id = None
    if do_upload and not args.skip_upload:

        logging.debug("Uploading {} -> {}".format(file_url, filepage))

        file_size = None
        if os.path.isfile(file_url):
            file_size = os.path.getsize(file_url)
            logging.debug(f'File size: {file_size // (1024 * 1024)}MB')

        if args.dry_run:
            logging.info(f"Dry run: skipped file upload to File{cms_fn}")
        else:
            wiki_uploader = StandardWikiUpload(upload_site)
            wiki_uploader.chunk_size = args.chunk_size
            wiki_uploader.simulate_stash_failure = args.simulate_stash_failure
            wiki_uploader.write_filepage_on_failure = True

            uploaded_ok = wiki_uploader.upload(cms_fn, file_url, desc)

            if not uploaded_ok:
                logging.debug('Normal Wiki upload failed')
                ssu_url = None
                if args.internet_archive:
                    tf_upload = UploadViaToolforgeSsh(upload_site)
                    tf_upload.upload(cms_fn, file_url, desc)

                if args.phab_ssu:

                    projs = []
                    extra_proj = os.getenv('PHAB_SSU_EXTRA_PROJECTS')
                    if extra_proj:
                        projs.append(extra_proj)

                    parent_task = os.getenv('PHAB_PARENT_TASK')

                    if not ssu_url:
                        raise RuntimeError("No URL for server-side-upload!")

                    phab_res = utils.phab_tasks.request_server_side_upload(
                        ssu_url,
                        wiki=args.ws_language + 'wikisource',
                        filename=cms_fn,
                        username=os.getenv('PHAB_USERNAME'),
                        file_desc=desc,
                        t278104=True,
                        extra_projs=projs,
                        parent_task=parent_task,
                        filesize=file_size,
                        extra=None)

                    phab_id = phab_res['result']['object']['id']

                    logging.info(f'Raised phab ticket T{phab_id}')

    indexpage = pywikibot.proofreadpage.IndexPage(ws_site, title='Index:' + cms_fn)

    index_content = make_index_content(r, filetype, phab_id=phab_id,
                                       lang=args.ws_language)
    print(index_content)

    summary = "Creating index page to match file"

    if args.skip_index:
        logging.debug(f'Skipping index creation for: {indexpage}')
    elif indexpage.exists() and args.exist_action == 'skip':
        logging.debug(f'Skipping index creation for existing page: {indexpage}')
    else:
        indexpage.text = index_content
        if not args.dry_run:
            indexpage.save(summary=summary, botflag=args.bot_flag)
        else:
            logging.info(f"Dry run: skipped index update, would have saved with summary '{summary}'")

    return True

class DataRow():

    def __init__(self, col_map, row):

        mapped_row = {}

        for col in col_map:
            value = row[col_map[col]].strip()

            # data normalisation
            if col.lower() == 'source':
                value = value.lower()

            mapped_row[col.lower()] = value
        self.r = mapped_row

    def get(self, key):

        if key not in self.r:
            return None
        return self.r[key].strip()

    def set(self, key, value):
        self.r[key] = value

    def get_bool(self, key, default):

        v = self.get(key)

        if not v:
            return default

        return v[0].lower() in ['y', 't', '1']


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--data_file', required=True,
                        help='The data file')
    parser.add_argument('-r', '--rows', nargs="+",
                        help='Rows to process')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='Do a dry run')
    parser.add_argument('-U', '--skip_upload', action='store_true',
                        help='Skip the file upload')
    parser.add_argument('-I', '--skip_index', action='store_true',
                        help='Skip index creation')
    parser.add_argument('-N', '--number', type=int,
                        help='Number `of (unskipped) rows to upload')
    parser.add_argument('-c', '--chunk-size', default='10M',
                        help='Upload chunk size (bytes); 0 to not use chunks, suffix M for megabytes')
    parser.add_argument('-m', '--max-lag', default=5, type=float,
                        help='Maxlag parameter default=5')
    parser.add_argument('-T', '--throttle', type=float, default=1,
                        help='Put throttle')
    parser.add_argument('-E', '--exist-action', type=str, default='skip',
                        help='What to do if a file exists: skip, update (info only) or overwrite')
    parser.add_argument('-b', '--bot-flag', action='store_true',
                        help='Use a bot flag for the index page creation')
    parser.add_argument('-F', '--file-dir',
                        help='The directory local files are loaded relative to')
    parser.add_argument('-p', '--proxy', action='store_true',
                        help='Use configured proxies')
    parser.add_argument('-J', '--internet-archive', action='store_true',
                        help='Upload to the Internet Archive')
    parser.add_argument('-P', '--phab-ssu', action='store_true',
                        help='File a Phabricator server-side upload request')
    parser.add_argument('-L', '--ws-language', default='en',
                        help='The Wikisource language subdomain')
    parser.add_argument('-X', '--simulate-stash-failure', action='store_true',
                        help='Simulate an immediate stash failure in Mediawiki'
                        ' (skip right to IA upload if configured with -J)')

    args = parser.parse_args()

    dotenv.load_dotenv()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("requests_cache").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    # logging.getLogger("pywiki").setLevel(pywikibot.logging.ERROR)

    pwbl = logging.getLogger("pywiki")
    pwbl.disabled = True

    if args.chunk_size.endswith("M"):
        args.chunk_size = int(args.chunk_size[:-1]) * 1024 * 1024
    else:
        args.chunk_size = int(args.chunk_size)

    if args.exist_action not in ['skip', 'update', 'overwrite']:
        raise ValueError("Bad value for the exist-action parameter")

    pywikibot.config.put_throttle = args.throttle

    if not args.file_dir:
        fdir = os.getenv('WSTOOLS_UPLOAD_SOURCE_DIR')

        if fdir:
            args.file_dir = fdir

    if not os.path.isabs(args.data_file):

        fdir = os.getenv('WSTOOLS_DATA_FILE_DIR')

        if fdir:
            args.data_file = os.path.join(fdir, args.data_file)

    print(args.data_file)

    # requests_cache.install_cache('uploadscans')

    pywikibot.config.maxlag = args.max_lag

    output = StringIO()

    Xlsx2csv(args.data_file, skip_trailing_columns=True,
             skip_empty_lines=True, outputencoding="utf-8").convert(output)

    output.seek(0)

    reader = csv.reader(output, delimiter=',', quotechar='"')

    head_row = next(reader)
    col_map = parse_header_row(head_row)

    pywikibot.config.socket_timeout = (10, 200)

    rows = utils.range_selection.get_range_selection(args.rows)

    uploaded_count = 0
    row_idx = 1

    for row in reader:

        row_idx += 1

        if rows is not None and row_idx not in rows:
            logging.debug("Skip row {}".format(row_idx))
            continue

        mapped_row = DataRow(col_map, row)

        # set defaults
        if not mapped_row.get('language'):
            mapped_row.set('language', 'en')

        handled = handle_row(mapped_row, args)

        if handled:
            uploaded_count += 1

        if args.number is not None and args.number == uploaded_count:
            logging.debug("Reached upload limit: {}".format(args.number))
            break


if __name__ == "__main__":
    main()
