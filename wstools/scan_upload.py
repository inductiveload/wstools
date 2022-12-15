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
import shutil
import multiprocessing
import traceback

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
import utils.row_map
import utils.author
import utils.choose_file
import utils.index_writer
import utils.ws_local
import utils.document_manip

import dl_book

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
            'until': 'expires',
            'reason': 'why'
        },
    },
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
        if w.code not in ['exists', 'was-deleted', 'exists-normalized', 'page-exists']:
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

        old_retries = pywikibot.config.max_retries

        try:
            if self.simulate_stash_failure:
                logging.debug(f"Simulating stash failure at {self.site}")
                raise pywikibot.exceptions.APIError('stashfailed', '')

            if file_url.startswith("http"):

                # do not retry - a timeout is normal
                pywikibot.config.max_retries = 4
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
        finally:
            pywikibot.config.max_retries = old_retries
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

def combine_linked(authors):

    links = ["[[{}|]]".format(a) for a in authors if a]

    return utils.string_utils.combine_list(links)


def combine_authors_linked(authors):

    links = ["[[Author:{}|]]".format(a) for a in authors if a]

    return utils.string_utils.combine_list(links)

def is_local(r):
    return bool(r.get('to_ws'))

def get_license_templates(r):

    lics = r.get('license').split('/')

    ws_local = utils.ws_local.WsLocal(r.get('ws_lang'))

    templates = []
    for lic in lics:

        lic = lic\
            .replace("—", "-")\
            .replace("–", "-")

        lic = lic.strip(' }{')

        # fix a common typo
        if lic.lower() in [
            "pd-old-expired-auto", "pd-us-expired-auto",
            "pd-us-auto-expired", "pd-old-auto-expired"
        ]:
            if is_local(r):
                lic, deathyear_param = ws_local.get_auto_pma_license()
            else:
                ## commons
                lic = "PD-old-auto-expired"
                deathyear_param = 'deathyear'

            deathyear = r.get('deathyear')
            if deathyear:
                lic += f'|{deathyear_param}={deathyear}'

        if is_local(r):
            lic = f'{{{{{lic}}}}}'
        else:
            lic = f'{{{{PD-scan|{lic}}}}}'

        templates.append(lic)

    return templates


def tidy_cats(cats):

    def tidy_cat(c):
        c = re.sub(r'^{{(.+?)}}', r'\1', c)
        c = re.sub(r'^Category\s*:\s*', '', c, re.I)
        c = re.sub(r'\[\[Category\s*:\s*(.*)\]\]', r'\1', c, re.I)
        return c.strip()

    cats = [tidy_cat(c) for c in cats]
    cats = [c for c in cats if c]

    # rm dupes
    cats = list(dict.fromkeys(cats))
    return cats

def get_cats(r, key, linkify) -> list:

    val = r.get(key)
    if not val:
        return []

    strs = tidy_cats(val.split('/'))

    if linkify:
        strs = [f'[[Category:{c}]]' for c in strs]

    return strs

def get_behalf(r):
    user = r.get('user')
    if user:
        return f' (on behalf of [[User:{user}]])'
    return ''

def make_description(r, typ):

    top_content = ''
    local = r.get_bool('to_ws', False)

    license = '\n'.join(get_license_templates(r))

    if local:
        subdomain = r.get('ws_lang')
        wsl = WS_LOCAL[subdomain]
        dnmtc = mwparserfromhell.nodes.template.Template(wsl['no_commons']['title'])

        if r.get('no_commons_until'):
            dnmtc.add(wsl['no_commons']['until'], r.get('no_commons_until'))

        if r.get('no_commons_reason'):
            dnmtc.add(wsl['no_commons']['reason'], r.get('no_commons_reason'))
        top_content = str(dnmtc)

    if r.get('source') == "ia":
        source = "{{{{IA|{iaid}}}}}".format(iaid=r.get('id'))
    elif r.get('source') == 'ht':
        source = "{{{{HathiTrust|{htid}|book}}}}".format(htid=r.get('id'))
    elif r.get('source') == "url":
        source = r.get('id')
    elif not r.get('source'):
        source = ''
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

    cats = "\n".join([f"[[Category:{x}]]" for x in tidy_cats(cats)])

    if r.get('vol_disp'):
        volume = r.get('vol_disp')
    elif r.get('volume'):
        volume = r.get('volume')
        if r.get('issue'):
            volume += ':' + r.get('issue')
    else:
        volume = ""

    if r.get('vol_detail'):
        volume += f' ({r.get("vol_detail")})'

    s = '''
== {{{{int:filedesc}}}} ==
{top_content}
{{{{Book
| Author       = {author}
| Editor       = {editor}
| Translator   = {translator}
| Illustrator  = {illustrator}
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
| Wikisource   = s:{ws_lang}:Index:{{{{PAGENAME}}}}
| Homecat      =
| Wikidata     =
| OCLC         = {oclc}
| ISBN         = {isbn}
| LCCN         = {lccn}
}}}}

== {{{{int:license-header}}}} ==
{license}

{cats}
'''.format(
        license=license,
        top_content=top_content,
        author=r.get('commons_author') or "",
        editor=r.get('commons_editor') or "",
        illustrator=r.get('commons_illustrator') or "",
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
        ws_lang=r.get('ws_lang'),
        img_page=r.get('img_pg') or "",
        cats=cats,
        oclc=r.get('oclc') or "",
        isbn=r.get('isbn') or "",
        lccn=r.get('lccn') or "",
        )

    return s


def get_commons_creator(wdqid):

    if not re.match(r'Q[0-9]+', wdqid):
        logging.debug("Not a Wikidata ID: {}".format(wdqid))
        return wdqid

    return "{{{{creator|wikidata={}}}}}".format(wdqid)


def get_wd_site_info(site, r, key, cats):
    """
    """

    if not r.get(key):
        return

    parts = r.get(key).split('/')
    ws_lang = r.get('ws_lang')

    commons_vals_wd = []
    commons_vals_str = []
    ws_vals = []

    repo = site.data_repository()

    items = []

    for part in parts:

        if re.match(r'Q[0-9]+', part):
            item = pywikibot.ItemPage(repo, part)
            author = utils.author.Author.from_wikidata(item, ws_lang)

            commons_vals_wd.append(get_commons_creator(part))

            ws_auth = author.ws_page
            if ws_auth:
                ws_vals.append(ws_auth)
            cats += author.commons_cats

            items.append(author)
        elif part:
            commons_vals_str.append(part)
            ws_vals.append('Author:' + part)

    r.set('ws_' + key, combine_linked(ws_vals))
    r.set('commons_' + key,
          "\n".join(commons_vals_wd) + "\n" + combine_linked(commons_vals_str))
    r.set(f'{key}_items', items)

def get_filename(r, ws_lang):

    fn = r.get('filename')

    ws_local = utils.ws_local.WsLocal(ws_lang)

    if not fn:
        fn = r.get('title')

        year = r.get('year')
        volume = r.get('volume')

        authors = r.get('author_items')
        if authors:
            sns = ', '.join([a.surname for a in authors if a.surname])
            fn += f' - {sns}'

        if year and not volume:
            fn += f' - {year}'

        if volume:
            fn += ' - ' + ws_local.format_filename_part('volume', volume)

    return fn


def sanitise_filename(fn):

    fn = fn\
        .replace("—", "-")\
        .replace("–", "-")

    return fn


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

class UploadContext():
    """
    Representation of the context for a single file's download/convert/upload process
    """

    tmp_dir = None
    target_size = None
    filename = None
    skip_dl = None
    source = None
    redownload_existing = False
    skip_convert = False
    keep_temp = False
    dl_def = None
    ext = None

    def __init__(self, r, basedir) -> None:
        self.r = r
        self.basedir = basedir

    def get_conversion_opts(self):

        src = self.r.get('source')

        if src == 'ht':
            return ["-b", ".png"]

        if src in ['ia', 'url']:
            return []

        raise NotImplementedError(f'Unknown source {src}')

    def get_output_file(self):
        of = self.dl_dir + (self.ext or '')
        return of

    def ws_lang(self):
        return self.r.get('ws_lang')

    def construct_dl_def(self):

        if self.dl_def:
            return self.dl_def

        mapped_row = self.r
        if not self.filename:
            filename = mapped_row.get('filename')

        source = mapped_row.get('source')

        dl_def = dl_book.DlDef(source, mapped_row.get('id'), filename)

        root, ext = os.path.splitext(filename)

        sanitised_id = dl_def.get_id().replace('/', '_')

        if ext.lower() in ['.pdf', '.djvu', '.tiff']:
            odir = root
        elif dl_def.filename:
            odir = dl_def.filename
        else:
            odir = sanitised_id

        self.dl_dir = os.path.join(self.basedir, odir)

        if mapped_row.get('access') == 'us':
            dl_def.use_proxy = True

        if mapped_row.get_bool('dl', False):
            dl_def.force_dl = True

        if mapped_row.get_bool('regen', False):
            dl_def.regenerate = True

        dl_def.skip_existing = not self.redownload_existing

        dl_def.exclude_pages = mapped_row.get_ranges('rm_pages')
        dl_def.include_pages = mapped_row.get_ranges('only_pages')

        self.dl_def = dl_def
        return dl_def

    def find_local_file(self, file_dir):

        # first see if we have a handy local file
        if file_dir:

            fileroots = [
                self.dl_def.get_id(),
                self.r.get('filename')
            ]

            fileroots = [r for r in fileroots if r]

            candidate_fns = itertools.product(
                ['.djvu', '.pdf'],
                fileroots
            )

            for ext, root in candidate_fns:
                print(ext, root)
                fn = os.path.join(file_dir, root + ext)
                if os.path.isfile(fn):
                    return fn

        return None

    def set_pagelist(self):
        r = self.r
        if not r.get('pagelist'):
            dl_def = self.construct_dl_def()
            if dl_def is not None:
                try:
                    pagelist = dl_def.get_pagelist()
                except:
                    logging.error("Failed to get pagelist")
                    pagelist = None

                inc_pages = None
                if r.get('only_pages'):
                    inc_pages = utils.range_selection.get_range_selection(
                        r.get('only_pages').split(','))

                exc_pages = None
                if r.get('rm_pages'):
                    exc_pages = utils.range_selection.get_range_selection(
                        r.get('rm_pages').split(','))

                if pagelist is not None:
                    pagelist.strip_pages(inc_pages, exc_pages)

            else:
                pagelist = None

            if not r.get("img_pg"):
                r.set('img_pg', '')

            if pagelist is None:
                r.set('pagelist', '<pagelist/>')
            else:
                page_offset = 0
                if r.get('pg_offset'):
                    page_offset = int(r.get('pg_offset'))

                if not r.get('img_pg') and pagelist.title_index is not None:
                    r.set('img_pg', str(pagelist.title_index - page_offset))

                r.set('pagelist', pagelist.to_pagelist_tag(page_offset))

class ScanUploader():

    def __init__(self, file_dir, args):
        self.use_proxy = False

        self.file_dir = file_dir

        self.upload_file = True
        self.write_index = True

        self.args = args

        self.defaults = {
            'ws_lang': 'en'
        }

    def find_better_url(self, r):

        tf_root = os.getenv('TOOLFORGE_FILE_STORE_URL')

        candidate_exts = ['.djvu', '.pdf']
        candidate_roots = [r.get('id'), r.get('filename')]
        candidate_roots = [r for r in candidate_roots if r]

        for ext, root in itertools.product(candidate_exts, candidate_roots):
            url = tf_root.rstrip('/') + '/' + root + ext
            r = requests.head(url)

            if r.status_code == 200:
                logging.debug(f'Found better URL: {url}')
                return url

        return None

    def acquire_file(self, uctx):
        """
        Invoke DL multi for the file download/conversion
        """

        dl_def = uctx.construct_dl_def()

        # first see if we have a handy local file
        uctx.downloaded = uctx.find_local_file(self.file_dir)

        # if not file_url:
        #     # first, check for better urls
        #     file_url = self.find_better_url(r)
        if uctx.skip_dl:
            uctx.downloaded = True
        elif not uctx.downloaded:
            # trigger download, get output dir
            uctx.downloaded = dl_def.do_download(uctx.dl_dir)

        logging.debug(f'Acquired file(s): {uctx.downloaded}')

    def convert_file(self, uctx):
        output_file = uctx.get_output_file()

        if (uctx.downloaded and
            os.path.isfile(uctx.downloaded) and
            os.path.splitext(uctx.downloaded)[1] in ['.djvu', '.pdf']):

            logging.debug('Skipping conversion because '
                          f'the source provided the file: {uctx.downloaded}')

            logging.debug('Downloaded: ' + uctx.downloaded)
            logging.debug('Output: ' + output_file)

            # we haven't got an extension yet
            if os.path.isdir(output_file):
                output_file += os.path.splitext(uctx.downloaded)[1]

            if uctx.downloaded != output_file:
                logging.debug(f'Moving to {output_file}')
                shutil.move(uctx.downloaded, output_file)
            return output_file

        if uctx.skip_convert:
            logging.debug('Skipping conversion due to --skip-convert')
            return output_file

        if not uctx.downloaded:
            logging.debug("Skipping convert: images not downloaded OK")
            return None

        if re.match(r'https?://', uctx.downloaded):
            logging.debug('No conversion required for URL source')
            return uctx.downloaded

        # we have to convert: assume this is going to a DJVU

        output_file = uctx.get_output_file() + ".djvu"
        cmd = ["./make_document.py",
                "-i", uctx.dl_dir,
                "-o", output_file,
                "-R",
                "-T", str(self.args.conversion_threads)]

        if uctx.tmp_dir is not None:
            cmd += ['-t', uctx.tmp_dir]

        if not uctx.keep_temp:
            cmd.append("-D")

        cmd += uctx.get_conversion_opts()

        if uctx.target_size is not None:
            cmd += ["-s", str(uctx.target_size)]

        if self.args.bitonal:
            cmd += ["-b", "*"]

        # very verbose also converts in verbose mode
        if self.args.verbose > 1:
            cmd.append('-' + 'v' * self.args.verbose)

        logging.debug(cmd)
        subprocess.check_call(cmd)

        return output_file

    def set_row_defaults(self, r):
        if not r.get('ws_lang'):
            r.set('ws_lang', self.defaults['ws_lang'])

    def handle_row(self, r):

        if r.get_bool('skip', False):
            logging.debug("Skipping row")
            return False

        basedir = os.getenv('WSTOOLS_OUTDIR')
        tmp_dir = "tmp"

        uctx = UploadContext(r, basedir)

        uctx.tmp_dir = os.path.join(basedir, tmp_dir)
        uctx.keep_temp = self.args.keep_temp
        uctx.skip_convert = self.args.skip_convert

        self.set_row_defaults(r)

        if r.get('size'):
            uctx.target_size = int(r.get('size'))
        elif self.args.target_size is not None:
            uctx.target_size = self.args.target_size

        if self.args.redownload_existing:
            uctx.redownload_existing = self.args.redownload_existing

        if self.args.hathi_direct is not None:
            uctx.hathi_direct = self.args.hathi_direct

        file_url = None

        if r.get('file'):

            # use local files if given
            file_url = r.get('file')

            if os.path.isdir(file_url):
                # path exists, but it's just a dir, so magically guess
                file_url = find_file(r, file_url)

            elif self.file_dir and not os.path.isabs(file_url):
                file_url = os.path.join(self.file_dir, file_url)

            # no actual file is OK if we're not going to upload it
            if not self.args.skip_upload and not file_url:
                raise RuntimeError(f'Cannot find file: {r.get("file")}')

            if file_url and os.path.isfile(file_url):
                logging.debug("Local file size {} MB: {}".format(
                    os.path.getsize(file_url) // (1024 * 1024), file_url))
        else:
            # we have no local URL, so now we should construct a download and
            # do it
            self.acquire_file(uctx)
            output_file = self.convert_file(uctx)

            if not output_file:
                raise RuntimeError('No local file and the source cannot provide one')

            file_url = output_file

        logging.debug("File source: {}".format(file_url))

        _, ext = os.path.splitext(file_url)

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

        # if we downloaded the file, we didn't have a chance to delete the pages
        if dl_file and r.get('rem_pg'):
            pages = utils.range_selection.get_range_selection(r.get('rem_pg'))
            pages = [int(x) for x in pages]
            utils.document_manip.remove_pages(dl_file, pages, ext=ext)

        uctx.set_pagelist()

        # if not r.get('oclc'):
        #     r.set('oclc', source.get_oclc())

        upload_to_ws = r.get_bool('to_ws', False)
        ws_lang = r.get('ws_lang')
        ws_site = pywikibot.Site(ws_lang, "wikisource")

        if upload_to_ws:
            uctx.upload_site = ws_site
        else:
            uctx.upload_site = pywikibot.Site("commons", "commons")

        if not r.get('year'):
            r.set('year', r.get('date'))

        autocats = []
        get_wd_site_info(ws_site, r, 'author', autocats)
        get_wd_site_info(ws_site, r, 'editor', autocats)
        get_wd_site_info(ws_site, r, 'translator', autocats)
        get_wd_site_info(ws_site, r, 'illustrator', autocats)

        if not r.get('filename'):
            r.set('filename', get_filename(r, ws_lang))

        if not r.get('filename').lower().endswith(ext.lower()):
            r.set('filename', r.get('filename') + ext)

        if not r.get('commonscats'):
            r.set('commonscats', '/'.join(autocats))

        filetype = ext[1:]
        desc = make_description(r, filetype)
        print(desc)

        uctx.description = desc

        # filter out nasties in the filename
        cms_fn = sanitise_filename(r.get('filename'))
        filepage = pywikibot.FilePage(uctx.upload_site, "File:" + cms_fn)

        do_upload = True

        try:
            filepage.get_file_url()
            has_image_info = filepage.exists()
        except pywikibot.exceptions.PageRelatedError:
            has_image_info = False

        if has_image_info and not self.args.skip_upload:
            logging.warning("File page exists: {}".format(cms_fn))

            if self.args.exist_action == 'skip':
                logging.info('Skipping file upload for {filepage}')
                do_upload = False
            elif self.args.exist_action == 'update':
                filepage.text = desc
                summary = 'Updating description from batch upload data'
                if not self.args.dry_run:
                    logging.info(f'Writing file info: {filepage}')
                    filepage.save(
                        summary=summary,
                        ignore_warnings=handle_write_filepage_warning
                    )
                else:
                    logging.info(f"Dry run: skipped description update, would have saved with message '{summary}'")

                do_upload = False

        phab_id = None
        if do_upload and self.upload_file:
            self.do_upload_file(uctx, file_url, filepage)

        self.create_index_page(r, ws_site, cms_fn, ws_lang, filetype, phab_id)

    def do_upload_file(self, uctx, file_url, filepage):
        logging.debug("Uploading {} -> {}".format(file_url, filepage))

        cms_fn = filepage.title()

        file_size = None
        if os.path.isfile(file_url):
            file_size = os.path.getsize(file_url)
            logging.debug(f'File size: {file_size // (1024 * 1024)}MB')

        if self.args.dry_run:
            logging.info(f"Dry run: skipped file upload to {filepage}")
        else:
            wiki_uploader = StandardWikiUpload(uctx.upload_site)
            wiki_uploader.chunk_size = self.args.chunk_size
            wiki_uploader.simulate_stash_failure = self.args.simulate_stash_failure
            wiki_uploader.write_filepage_on_failure = True

            uploaded_ok = wiki_uploader.upload(filepage.title(with_ns=False),
                                               file_url,
                                               uctx.description)

            if not uploaded_ok:
                logging.debug('Normal Wiki upload failed')
                ssu_url = None
                if self.args.internet_archive:
                    tf_upload = UploadViaToolforgeSsh(uctx.upload_site)
                    tf_upload.upload(cms_fn, file_url, uctx.description)

                if self.args.phab_ssu:
                    phab_id = self.raise_phab_ticket(
                        ssu_url, uctx.ws_lang(), cms_fn, uctx.description, file_size)

    def raise_phab_ticket(self, ssu_url, lang, filename, description, file_size):

        projs = []
        extra_proj = os.getenv('PHAB_SSU_EXTRA_PROJECTS')
        if extra_proj:
            projs.append(extra_proj)

        parent_task = os.getenv('PHAB_PARENT_TASK')

        if not ssu_url:
            raise RuntimeError("No URL for server-side-upload!")

        phab_res = utils.phab_tasks.request_server_side_upload(
            ssu_url,
            wiki=lang + 'wikisource',
            filename=filename,
            username=os.getenv('PHAB_USERNAME'),
            file_desc=description,
            t278104=True,
            extra_projs=projs,
            parent_task=parent_task,
            filesize=file_size,
            extra=None)

        phab_id = phab_res['result']['object']['id']

        logging.info(f'Raised phab ticket T{phab_id}')
        return phab_id

    def create_index_page(self, r, site, cms_fn, lang, filetype, phab_id):

        indexpage = pywikibot.proofreadpage.IndexPage(site, title='Index:' + cms_fn)

        writer = utils.index_writer.IndexWriter(lang)

        index_content = writer.make_index_content(r, filetype, phab_id=phab_id)
        print(index_content)

        summary = 'Creating index page to match file' + get_behalf(r)

        if not self.write_index:
            logging.debug(f'Skipping index creation for: {indexpage}')
        elif indexpage.exists() and self.args.exist_action == 'skip':
            logging.debug(f'Skipping index creation for existing page: {indexpage}')
        else:
            indexpage.text = index_content
            if not self.args.dry_run:
                indexpage.save(summary=summary, botflag=self.args.bot_flag)
            else:
                logging.info("Dry run: skipped index update, "
                             f"would have saved with summary '{summary}'")

        return True

    def upload_row(self, mapped_row):
        # set defaults
        mapped_row.set_default('language', 'en')
        mapped_row.set_default('ws', 'en')
        mapped_row.set_default('access', 'us')

        # data normalisation
        mapped_row.apply('source', str.lower)

        print(mapped_row.dump())

        return self.handle_row(mapped_row)

    def upload(self, rows, limit=None):

        uploaded_count = 0
        row_idx = 1

        for row in rows:

            row_idx += 1

            handled = False
            try:
                handled = self.upload_row(row)
            except KeyboardInterrupt:
                break
            except Exception as e:
                traceback.print_exception(e)
                logging.error(f'Failed to upload row: {row.index}')
                pass

            if handled:
                uploaded_count += 1

            if limit is not None and limit == uploaded_count:
                logging.debug(f'Reached upload limit: {limit}')
                break


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
    parser.add_argument('-F', '--file-dir',
                        help='The directory local files are loaded relative to')

    # DL options
    parser.add_argument('-x', '--redownload-existing', action='store_true',
                        help='Redownload existing image files')
    parser.add_argument('--hathi-direct', action='store_true',
                        help='For Hathi downloads, do not use the Data API')
    parser.add_argument('-p', '--proxy', action='store_true',
                        help='Use configured proxies')

    # Conversion options
    parser.add_argument('-S', '--target-size', type=int,
                        help='Target file size in MB (approximate)')
    parser.add_argument('-t', '--conversion-threads', type=int,
                        help='Number of conversion threads')
    parser.add_argument('-k', '--keep-temp', action='store_true',
                        help='Keep temporary converted files')
    parser.add_argument('-C', '--skip-convert', action='store_true',
                        help='Skip conversion if possible')
    parser.add_argument('-B', '--bitonal', action='store_true',
                        help='Enforce bitonal outputs')

    # Upload options
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

    args.conversion_threads = args.conversion_threads or max(1, multiprocessing.cpu_count() - 2)

    if not args.file_dir:
        fdir = os.getenv('WSTOOLS_UPLOAD_SOURCE_DIR')

        if fdir:
            args.file_dir = fdir

    args.data_file = utils.choose_file.choose_file(args.data_file,
        [os.getenv('WSTOOLS_DATA_FILE_DIR')]
    )

    logging.debug(f'Data file: {args.data_file}')

    # requests_cache.install_cache('uploadscans')

    pywikibot.config.maxlag = args.max_lag
    pywikibot.config.socket_timeout = (20, 200)

    rows = utils.row_map.get_rows(args.data_file, args.rows)

    su = ScanUploader(args.file_dir, args)

    su.upload_file = not args.skip_upload
    su.write_index = not args.skip_index

    su.upload(rows, args.number)


if __name__ == "__main__":
    main()
