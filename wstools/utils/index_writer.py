"""
Utility for turning an amorphous row map into an index page
"""

import utils.ws_local

import mwparserfromhell
import re

def process_oclc(oclc):

    if oclc is None:
        return None

    if 'worldcat.org' in oclc:
        return oclc.split('/')[-1]

    return oclc

def get_sortkey(s):
    titlewords = s.split()
    if titlewords[0].lower() in ["the", "a", "an"]:
        key = " ".join(titlewords[1:]) + ", " + titlewords[0]
    else:
        key = ""
    return key

class IndexWriter:

    def __init__(self, lang) -> None:
        self.ws_local = utils.ws_local.WsLocal(lang)

    def make_index_content(self, r, typ, phab_id=None):


        field_map = self.ws_local.get_index_field_map()
        format_strings = self.ws_local.get_filename_format_strings()

        vlist = r.get('vollist') or ""

        if vlist and not vlist.startswith('{{') and not vlist.strip()[0] in ('*:['):
            vlist = '{{' + vlist + '}}'

        title = r.get('title')
        subtitle = r.get('subtitle') or ""

        volume = ''
        if r.get('volume'):

            subpage = r.get('subpage')
            if not subpage:
                subpage = "Volume " + r.get('volume')

            subpage_disp = r.get('vol_disp') or subpage

            # append issue if needed
            issue = r.get('issue')
            if issue:
                if not r.get('subpage'):
                    subpage += '/' + format_strings['issue'].format(issue)
                if not r.get('vol_disp'):
                    subpage_disp += ', ' + format_strings['issue'].format(issue)

            volume = f'[[{title}/{subpage}|{subpage_disp}]]'

        elif r.get('subpage') and r.get('vol_disp'):
            # it's not a "volume" as such, but still needs a sub-work-level link
            subpage = r.get('subpage')
            subpage_disp = r.get('vol_disp') or subpage

            volume = f'[[{title}/{subpage}|{subpage_disp}]]'

        if volume and r.get('vol_detail'):
            volume += " ({})".format(r.get('vol_detail'))

        # linkify the title
        if r.get('title_disp') is None:
            title = f'[[{title}]]'
        else:
            title_disp = r.get('title_disp')
            title = f'[[{title}|{title_disp}]]'

        # This wikisource has no volume field
        if volume and 'volume' not in field_map:
            title = title + ", " + volume

        year = r.get('year') or (r.get('date') or "")
        key = get_sortkey(title)

        remarks = ''
        if phab_id:
            remarks = f'Pending server-side upload: [[phab:T{phab_id}]]'

        template = mwparserfromhell.nodes.Template(
            ":MediaWiki:Proofreadpage_index_template"
        )

        # for all the fields in the target wiki index template
        for field in field_map:

            value = None
            if field == 'type':
                value = self.ws_local.get_index_field_default('type')
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
            elif field == 'image':
                value = r.get('img_pg') or ""
            elif field == 'progress':
                value = r.get('progress') or self.ws_local.get_index_field_default('progress')
            elif field == 'pages':
                value = r.get('pagelist') or ""
            elif field == 'remarks':
                value = remarks
            elif field == 'wikidata':
                value = r.get('wikidata') or ""
            elif field == 'volumes':
                value = vlist
            elif field == 'transclusion':
                value = r.get('transclusion') or self.ws_local.get_index_field_default('transclusion')
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

            elif field == 'file_source':
                value = self.ws_local.format_source(r.get('source'), r.get('id'))

            elif field == 'oclc':
                value = process_oclc(r.get('OCLC')) or ""
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
                # get the localised parameter name
                param = field_map[field]

                value = self.ws_local.format_index_field(field, value)

                template.add(param, value + '\n')

        template = re.sub(r'\n\n+', '\n', str(template))

        # PWB doesn't link this
        categories = [] # get_cats(r, 'ws_cats', linkify=True)

        if categories:
            template += '\n' + '\n'.join(categories)

        return template