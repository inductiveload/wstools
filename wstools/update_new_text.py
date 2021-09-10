#! /usr/bin/env python3

import argparse
import logging

import pywikibot
import mwparserfromhell
import json
import re


class NewTextProcessor():

    def __init__(self, lang, page):
        self.lang = lang
        self.page = page

    def process_authors(self, arg):
        """
        Attempt to intuit a list of authors from a template argument
        """

        links = arg.value.filter_wikilinks()

        if len(links) == 0:
            return arg.value.strip_code()

        def map_author(link):

            text = link.title.strip_code()

            if text and text.endswith(')'):
                text = re.sub(r'^((.*) \(.*?\))$', r'\1|\2', text)

            text = text.replace("Author:", '')

            for portal_hint in ['Parliament, Council, Government, House of']:
                for portal_hint in text:
                    text = 'Portal:' + text
                    break

            return text

        auths = list(map(map_author, links))
        return auths

    def run(self, section):

        site = pywikibot.Site(self.lang, 'wikisource')
        page = pywikibot.Page(site, self.page)

        wikicode = mwparserfromhell.parse(page.text)

        item_name = 'new texts/item'

        data = []

        sections = wikicode.get_sections(matches=section)
        templates = sections[0].filter_templates()

        for instance in [x for x in templates if x.name.strip().lower() == item_name]:

            title = instance.get(1, None)
            if not title:
                title = instance.get('title', None)

            author = instance.get(2, None)
            if not author:
                author = instance.get('author', None)

            date = instance.get(3, None)
            if not date:
                date = instance.get('date', None)

            item_type = instance.get('type', None)

            display = instance.get('display', None)
            translator = instance.get('translator', None)
            editor = instance.get('editor', None)
            illustrator = instance.get('illustrator', None)

            json_item = {
                'title': title.value.strip_code(),
            }

            def set_author_field(item, field, var):
                if var:
                    item[field] = self.process_authors(var)

            set_author_field(json_item, 'author', author)
            set_author_field(json_item, 'translator', translator)
            set_author_field(json_item, 'editor', editor)
            set_author_field(json_item, 'illustrator', illustrator)

            if date:
                json_item['year'] = date.value.strip_code()

            if display:
                json_item['display'] = display.value.strip_code()

            if item_type:
                json_item['type'] = item_type.value.strip_code()

            data.append(json_item)

        return data


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-p', '--page', default="Template:New texts",
                        help='The page to read data from')
    parser.add_argument('-l', '--lang', default='en',
                        help='Wikisource lang code')
    parser.add_argument('-s', '--section', default='json',
                        help='The section filter')
    args = parser.parse_args()

    # log_level = logging.DEBUG if args.verbose else logging.INFO
    # logging.basicConfig(level=log_level)

    ntp = NewTextProcessor(args.lang, args.page)
    data = ntp.run(args.section)
    s = json.dumps(data, indent="\t")
    print(s)


if __name__ == "__main__":
    main()
