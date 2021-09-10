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

import utils.pagelist
import utils.ia_source
import utils.ht_source
import utils.ht_api
import utils.commonsutils
import utils.string_utils
import utils.ia_upload
import utils.phab_tasks

import requests
import requests_cache


import pywikibot
import pywikibot.proofreadpage
import mwparserfromhell

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


def get_value(r, keys):

    for k in keys:

        if k in r and r[k] is not None and r[k]:
            return r[k]

    return None


def is_trueish(v, default=False):

    if not v:
        return default

    return v.lower() in ['y', 'yes', 'true', '1']


def make_index_content(r, typ, phab_id=None):

    publisher = r['publisher'] if 'publisher' in r else ""
    progress = "X"
    vlist = r['vollist'] if 'vollist' in r else ""
    city = r['city'] if 'city' in r else ""

    title_val = get_value(r, ['mainspace', 'title'])

    title = "''[[{}]]''".format(title_val)

    volume = ''
    if 'volume' in r and r['volume']:

        if 'subpage' in r and r['subpage']:
            subpage = r['subpage']
        else:
            subpage = "Volume " + r['volume']

        subpage_disp = r['subpage_disp'] if 'subpage_disp' in r else subpage

        volume = "[[{}/{}|{}]]".format(title_val, subpage, subpage_disp)

        if 'vol_detail' in r and r['vol_detail']:
            volume += " ({})".format(r['vol_detail'])

    year = r['year'] if 'year' in r else (r['date'] if 'date' in r else "")

    pages = r['pagelist']

    titlewords = title_val.split()
    if titlewords[0].lower() in ["the", "a", "an"]:
        key = " ".join(titlewords[1:]) + ", " + titlewords[0]
    else:
        key = ""

    remarks = ''
    if phab_id:
        remarks = f'Pending server-side upload: [[phab:T{phab_id}]]'

    s = """{{{{:MediaWiki:Proofreadpage_index_template
|Type=book
|Title={title}
|Language={language}
|Volume={volume}
|Author={author}
|Translator={translator}
|Editor={editor}
|Illustrator=
|School=
|Publisher={publisher}
|Address={city}
|Year={year}
|Key={key}
|ISBN=
|OCLC={oclc}
|LCCN=
|BNF_ARK=
|ARC=
|Source={source}
|Image={pg_img}
|Progress={progress}
|Pages={pages}
|Volumes={volume_list}
|Remarks={remarks}
|Width=
|Css=
|Header=
|Footer=
}}}}""".format(
        title=title,
        language=r['language'],
        volume=volume,
        author=r['ws_author'],
        editor=r['ws_editor'],
        translator=r['ws_translator'],
        publisher=publisher,
        city=city,
        year=year,
        source=typ,
        pg_img=r['img_pg'] if 'img_pg' in r else "",
        progress=progress,
        pages=pages,
        volume_list=vlist,
        key=key,
        oclc=r['oclc'] if 'oclc' in r else "",
        remarks=remarks
    )

    return s


def has(r, key):
    return (key in r) and r[key]


def make_description(r, typ):

    lic = r['license'].replace("—", "-").replace("–", "-")

    if lic == "PD-old-auto-expired" and 'deathyear' in r:
        lic += "|deathyear=" + r['deathyear']

    top_content = ''
    local = 'to_ws' in r and r['to_ws'].lower() not in ['n', 'no']

    if local:
        wsl = WS_LOCAL['en']
        dnmtc = mwparserfromhell.nodes.template.Template(wsl['no_commons']['title'])

        if 'no_commons_until' in r and r['no_commons_until']:
            dnmtc.add(wsl['no_commons']['until'], r['no_commons_until'])

        if 'no_commons_reason' in r and r['no_commons_reason']:
            dnmtc.add(wsl['no_commons']['reason'], r['no_commons_reason'])
        top_content = str(dnmtc)

    if local:
        license = f'{{{{{lic}}}}}'
    else:
        license = f'{{{{PD-scan|{lic}}}}}'

    if r['source'] == "ia":
        source = "{{{{IA|{iaid}}}}}".format(iaid=r['id'])
    elif r['source'] == 'ht':
        source = "{{{{HathiTrust|{htid}|book}}}}".format(htid=r['id'])
    elif r['source'] == "url":
        source = r['id']
    else:
        raise("Unknown source: {}".format(r['source']))

    langname = utils.commonsutils.lang_cat_name(r['language'])

    cats = []

    if not local:
        if typ == "djvu":
            cats.append("DjVu files in {lang}".format(lang=langname))
        else:
            cats.append("PDF files in {lang}".format(lang=langname))

    if 'commonscats' in r and r['commonscats']:
        cats += r['commonscats'].split("/")

    date = r['date'] if has(r, 'date') else ""
    year = r['year'] if has(r, 'year') else date

    if not date and year:
        date = year

    cats = "\n".join(["[[Category:{}]]".format(x) for x in cats])

    if 'vol_disp' in r and r['vol_disp']:
        volume = r['vol_disp']
    elif 'volume' in r and r['volume']:
        volume = r['volume']
    else:
        volume = ""

    if 'vol_detail' in r and r['vol_detail']:
        volume += " ({})".format(r['vol_detail'])

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
}}}}

== {{{{int:license-header}}}} ==
{license}

{cats}
""".format(
        license=license,
        top_content=top_content,
        author=r['commons_author'],
        editor=r['commons_editor'],
        translator=r['commons_translator'],
        title=r['title'] if 'title' in r else "",
        subtitle=r['subtitle'] if 'subtitle' in r else "",
        volume=volume,
        publisher=r['publisher'] if 'publisher' in r else "",
        printer=r['printer'] if 'printer' in r else "",
        city=r['city'] if 'city' in r else "",
        date=date,
        language=r['language'],
        source=source,
        img_page=r['img_pg'] if 'img_pg' in r else "",
        cats=cats,
        oclc=r['oclc'] if 'oclc' in r else "",
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
    try:
        parts = r[key].split("/")
    except KeyError:
        parts = []

    if not parts or not re.match("Q[0-9]+", r[key]):
        r['commons_' + key] = utils.string_utils.combine_list(parts)
        r['ws_' + key] = combine_authors_linked(parts)

    else:
        repo = site.data_repository()

        r['commons_' + key] = "\n".join(["{{{{creator|wikidata={}}}}}".format(a) for a in parts])
        r['ws_' + key] = combine_linked([get_wd_site_author(repo, a) for a in parts])


def handle_warning(warnings):

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


def handle_row(r, args):

    print(r)

    if 'skip' in r and r['skip'] not in ["", "n", "no"]:
        logging.debug("Skipping row")
        return False

    if r['source'] == "ia":
        source = utils.ia_source.IaSource(r['id'])

        if 'prefer_pdf' in r and r['prefer_pdf']:
            source.prefer_pdf = True
    elif r['source'] == "ht":
        dapi = utils.ht_api.DataAPI(proxies=args.proxy)
        source = utils.ht_source.HathiSource(dapi, r['id'])
    else:
        source = None

    if source is not None:
        # normalise the ID
        r['id'] = source.get_id()

    file_url = None

    if 'file' in r and r['file']:

        # use local files if given
        file_url = r['file']

        if args.file_dir and not os.path.isabs(file_url):
            file_url = os.path.join(args.file_dir, file_url)

        logging.debug("Local file size {} MB: {}".format(
            os.path.getsize(file_url) // (1024 * 1024), file_url))
    else:

        # first see if we have a handy local file
        if args.file_dir:
            candidate_fns = itertools.product(
                [
                    utils.source.sanitise_id(r['id']),
                    r['filename']
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
    if 'dl' in r and r['dl'].startswith("y") and file_url.startswith("http"):
        # actually download the file
        logging.debug("Downloading file: {}".format(file_url))

        req = requests.get(file_url)
        req.raise_for_status()

        dl_file = "/tmp/dlfile" + ext

        with open(dl_file, "wb") as tf:
            tf.write(req.content)
        logging.debug("Wrote file to: {}".format(dl_file))

        file_url = dl_file

    if dl_file and 'rem_pg' in r:
        pages = split_any(r['rem_pg'], [" ", ","])

        print(pages)
        pages = [int(x) for x in pages]
        pages.sort(reverse=True)

        for p in pages:
            if ext == ".djvu":
                cmd = ["djvm", "-d", dl_file, str(p)]
                logging.debug("Deleting page {}".format(p))
                subprocess.call(cmd)

    if 'pagelist' not in r or not r['pagelist']:
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

        if "img_pg" not in r:
            r["img_pg"] = ""

        if pagelist is not None:

            page_offset = 0
            if 'pg_offset' in r and r['pg_offset']:
                page_offset = int(r['pg_offset'])

            if not r["img_pg"] and pagelist.title_index is not None:
                r["img_pg"] = str(pagelist.title_index - page_offset)

            r['pagelist'] = pagelist.to_pagelist_tag(page_offset)
        else:
            r['pagelist'] = "<pagelist/>"

    # if 'oclc' not in r or not r['oclc']:

    #     r['oclc'] = source.get_oclc()

    if 'year' not in r:
        r['year'] = r['date']

    if not r['filename'].lower().endswith(ext.lower()):
        r['filename'] += ext

    ws_site = pywikibot.Site(args.ws_language, "wikisource")

    upload_to_ws = 'to_ws' in r and is_trueish(r['to_ws'], False)

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
    cms_fn = r['filename'].replace("—", "-").replace("–", "-")
    filepage = pywikibot.FilePage(upload_site, "File:" + cms_fn)

    logging.debug(filepage)

    do_upload = True

    if filepage.exists():
        logging.warning("File page exists: {}".format(cms_fn))

        if args.exist_action == 'skip':
            logging.info("Skipping file")
            return False

        if args.exist_action == 'update':
            filepage.text = desc

            if not args.dry_run:
                filepage.save("Updating description from batch upload data")
            else:
                logging.info("Dry run: skipped description update")

            do_upload = False

    phab_id = None
    if do_upload and not args.skip_upload:

        logging.debug("Uploading {} -> {}".format(file_url, filepage))

        if args.dry_run:
            logging.info("Dry run: skipped file upload to {}")
        else:
            try:
                raise pywikibot.exceptions.APIError('stashfailed', '')
                if file_url.startswith("http"):
                    upload_site.upload(filepage, source_url=file_url,
                                       comment=desc,
                                       report_success=False,
                                       ignore_warnings=handle_warning)
                else:
                    upload_site.upload(filepage, source_filename=file_url,
                                       comment=desc, report_success=False,
                                       ignore_warnings=handle_warning,
                                       chunk_size=args.chunk_size,
                                       asynchronous=True)
            except pywikibot.exceptions.APIError as e:

                if e.code in ['uploadstash-file-not-found', 'stashfailed']:

                    logging.info(
                            f'WMF upload failed with {e.code}: uploading to IA')

                    ssu_url = None
                    ssu_size = None
                    if args.internet_archive:
                        logging.debug(f'Attempting IA upload of {file_url}')
                        ia_id, ia_file = utils.ia_upload.upload_file(
                            file_url,
                            cms_fn,
                            r['title'],
                            author=r['author'] if 'author' in r else None,
                            editor=r['editor'] if 'editor' in r else None,
                            date=r['year'],
                            src_url=None
                        )

                        if os.path.isfile(file_url):
                            ssu_size = os.path.getsize(file_url)

                        ssu_url = f'https://archive.org/download/{ia_id}/{ia_file}'

                    if args.phab_ssu:

                        projs = []
                        extra_proj = os.getenv('PHAB_SSU_EXTRA_PROJECTS')
                        if extra_proj:
                            projs.append(extra_proj)

                        parent_task = os.getenv('PAHB_PARENT_TASK')

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
                            filesize=ssu_size,
                            extra=None)

                        phab_id = phab_res['result']['object']['id']

                        logging.info(f'Raised phab ticket T{phab_id}')
                else:
                    # something else went wrong
                    raise(e)

    indexpage = pywikibot.proofreadpage.IndexPage(ws_site, title='Index:' + cms_fn)

    index_content = make_index_content(r, filetype, phab_id=phab_id)

    print(index_content)

    summary = "Creating index page to match file"

    if not args.skip_index:

        if not args.dry_run:
            indexpage.put(index_content, summary=summary, botflag=args.bot_flag)
        else:
            logging.info("Dry run: skipped index update")

    return True


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--data_file', required=True,
                        help='The data file')
    parser.add_argument('-r', '--rows', type=int, nargs="+",
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
                        help='Upload chunk size (MB); 0 to not use chunks')
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

    uploaded_count = 0
    row_idx = 1

    for row in reader:

        row_idx += 1

        if args.rows is not None and row_idx not in args.rows:
            logging.debug("Skip row {}".format(row_idx))
            continue

        mapped_row = {}

        for col in col_map:
            mapped_row[col.lower()] = row[col_map[col]].strip()

        handled = handle_row(mapped_row, args)

        if handled:
            uploaded_count += 1

        if args.number is not None and args.number == uploaded_count:
            logging.debug("Reached upload limit: {}".format(args.number))
            break


if __name__ == "__main__":
    main()
