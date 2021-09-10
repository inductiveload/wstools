#! /usr/bin/env python3

import argparse
import logging

import pywikibot
import yaml
import re
import os


TYPES = {
    "headpiece": {
        "desc": "Headpiece from {src}",
        "cats": ["Headpieces (book illustration)"],
        "title_comp": "headpiece",
    },
    "endpiece": {
        "desc": "Endpiece from {src}",
        "cats": ["Endpieces (book illustration)"],
        "title_comp": "endpiece",
    },
    "nameplate": {
        "desc": "Nameplate from {src}",
        "cats": ["Newspaper nameplates"],
        "title_comp": "nameplate",
    },
    "divider": {
        "desc": "Text divider from {src}",
        "cats": ["Text dividers"],
        "title_comp": "divider",
    },
    "frontispiece": {
        "desc": "Frontispiece from {src}",
        "cats": ["Frontispieces"],
        "title_comp": "frontispiece",
    },
    "fleuron": {
        "desc": "Fleuron from {src}",
        "cats": ["Fleurons"],
        "title_comp": "fleuron",
    },
    "title": {
        "desc": "Title from {src}",
        "cats": ["Titles (text)"],
        "title_comp": "title",
    },
}


def construct_info(d, page, index):

    t = ""

    t += "=={{int:filedesc}}==\n"

    flink = "''[[:File:{f}|{t}]]''".format(f=d['index'], t=d['title'])

    if 'date' in d:
        flink += " ({})".format(d['date'])

    description = ""

    if page:
        if page.lower() in ["title"]:
            source = "title page"
        else:
            source = "page {}".format(page)

        source += " of {f}".format(f=flink)
    else:
        source = "{f}".format(f=flink)

    if 'type' in d:
        if d['type'] in TYPES:
            description = TYPES[d['type']]['desc'].format(src=source)
        elif d['type'] == "initial":
            description = "Initial '{i}' from {src}".format(
                i=d['initial'], src=source)

    elif 'desc' in d:
        description = d['desc']

        if description[-1] != '.':
            description += '.'

        description += " From {src}".format(src=source)
    else:
        description = "Illustration from {src}".format(src=source)

    if 'caption' in d and d['caption'] is not None:
        description += ". Caption: {}.".format(d['caption'])

    authors = "\n\n".join(d['author'])

    info = ""

    if "pre_desc" in d:
        info += d['pre_desc'] + "\n\n"

    description = "{{en|1=" + description + "}}"

    info += """{{{{information
 | description = {d}
 | date = {date}
 | source = {src}
 | author = {a}
 | permission =
 | other versions =
}}}}
 """.format(
        d=description,
        date=d['date'],
        src=d['source'],
        a=authors
    )

    t += info

    t += "\n=={{int:license-header}}==\n"

    for lic in d['licence']:
        t += lic + "\n"

    t += "\n"

    for c in d['categories']:
        t += "[[Category:" + c + "]]\n"

    if 'categorise' not in d or d['categorise']:

        if 'type' in d:
            if d['type'] in TYPES:
                t += "\n".join(["[[Category:{}]]".format(c) for c in TYPES[d['type']]['cats']])
            if d['type'] == "initial":
                t += "[[Category:{} as an initial]]\n".format(d['initial'])
    return t


def get_file_title(d, page, index):

    index_str = ""
    if index is not None:
        if 'index_pattern' in d:
            index_str = d['index_pattern']
        else:
            index_str = "-{index}"

        index_str = index_str.format(page=page, index=index)

    if 'filename_pattern' in d:

        page_str = d['filename_pattern'].format(
            index=index_str, page=page)

    else:
        page_str = "{title}".format(title=d['title'])

        if d['date_in_title']:
            page_str += " ({date})".format(date=d['date'])

        if 'type' in d:
            if d['type'] in TYPES:
                page_str += " - " + TYPES[d['type']]['title_comp']
            elif d['type'] == "initial":
                page_str += " - initial {}".format(d['initial'])

        if page:
            page_str += " - "
            if page.lower() in ["title"]:
                page_str += "title page"
            else:
                page_str += "page {page}{index}".format(page=page, index=index_str)

    return page_str


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-i', '--info', required=True,
                        help='The data file')
    parser.add_argument('-p', '--page',
                        help='The page the image comes from')
    parser.add_argument('-d', '--is-divider', action="store_true",
                        help='Is this a text divider')
    parser.add_argument('-H', '--is-headpiece', action="store_true",
                        help='Is this a text headpiece')
    parser.add_argument('-E', '--is-endpiece', action="store_true",
                        help='Is this a text endpiece')
    parser.add_argument('-F', '--is-fpiece', action="store_true",
                        help='Is this a text frontispiece')
    parser.add_argument('-N', '--is-nameplate', action="store_true",
                        help='Is this a periodical nameplate')
    parser.add_argument('-l', '--is-fleuron', action="store_true",
                        help='Is this a fleuron')
    parser.add_argument('-t', '--is-title', action="store_true",
                        help='Is this a title')
    parser.add_argument('-I', '--initial',
                        help='Illustrated initial')
    parser.add_argument('-C', '--caption',
                        help='Image caption')
    parser.add_argument('-s', '--img_size',
                        help='Default image size for the example')
    parser.add_argument('-c', '--auto-cat', action="store_true",
                        help='Auto-construct a category')
    parser.add_argument('-n', '--dry-run', action="store_true",
                        help='Dry run upload?')
    parser.add_argument('-f', '--file', required=True,
                        help='File to upload')
    parser.add_argument('-D', '--date-in-title', action="store_true",
                        help='Add date to title')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("oauthlib").setLevel(logging.WARNING)
    logging.getLogger("pywiki").setLevel(logging.WARNING)

    pwbl = logging.getLogger("pywiki")
    pwbl.disabled = True

    with open(args.info) as df:

        info = yaml.load(df, Loader=yaml.FullLoader)

    if args.is_divider:
        info['type'] = 'divider'
    elif args.is_endpiece:
        info['type'] = 'endpiece'
    elif args.is_headpiece:
        info['type'] = 'headpiece'
    elif args.is_nameplate:
        info['type'] = 'nameplate'
    elif args.is_fpiece:
        info['type'] = 'frontispiece'
    elif args.is_fleuron:
        info['type'] = 'fleuron'
    elif args.is_title:
        info['type'] = 'title'
    elif args.initial is not None:
        info['type'] = 'initial'
        info['initial'] = args.initial.upper()

    if 'categories' not in info:
        info['categories'] = []

    info['caption'] = args.caption

    info['date_in_title'] = args.date_in_title

    if args.auto_cat or 'autocat' in info and info['autocat']:

        autocat = "{} ({})".format(info['title'], info['date'])
        logging.debug("Constructing category: " + autocat)

        info['categories'].append(autocat)

    m = re.search(r"(?:[Pp]|[Pp]age|[Pp]g)[ _]?(([0-9]+|[ivxlc]+)(?:-([0-9]+))?)\b", args.file)

    if m:
        print(m, m[1])
        page = m[1]
    else:
        page = args.page if args.page else ""

    parts = page.split("-")

    index = None
    if len(parts) > 1:
        page = parts[0]
        index = int(parts[1])

    info_str = construct_info(info, page, index)

    print(info_str)

    tgt_name = get_file_title(info, page, index)

    _, file_extension = os.path.splitext(args.file)

    tgt_name += file_extension

    print("Filename:", tgt_name)

    if 'dest' in info and info['dest'] == "enws":
        upload_site = pywikibot.Site("en", "wikisource")
    else:
        upload_site = pywikibot.Site("commons", "commons")

    filepage = pywikibot.FilePage(upload_site, "File:" + tgt_name)

    # single upload doesn't need a PT
    pywikibot.config.put_throttle = 0

    if not args.dry_run:
        upload_site.upload(filepage, source_filename=args.file,
                           comment=info_str, report_success=False,
                           ignore_warnings=True,
                           chunk_size=10*1024*1024)

    if args.img_size:
        img_size = args.img_size
    elif 'img_size' in info:
        img_size = info['img_size']
    else:
        img_size = "200"

    if 'type' in info and info['type'] == 'initial':
        img_size = 100
        helper_str = "{{{{dropinitial|alt={i}|[[File:{fn}|{px}px]]}}}}".format(
            i=info['initial'], fn=tgt_name, px=img_size)
    else:
        helper_str = "[[File:{fn}|center|{px}px]]".format(fn=tgt_name, px=img_size)

    print(helper_str)


if __name__ == "__main__":
    main()
