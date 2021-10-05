#! /usr/bin/env python3

import argparse
import logging

import pywikibot
import mwparserfromhell
import json
import re


class EntryProcessor():

    def __init__(self):
        self.nowiki = False

    def process_authors(self, arg):
        """
        Attempt to intuit a list of authors from a template argument

        Returns list of authors and whether there were links in the text
        """

        links = arg.value.filter_wikilinks()

        if len(links) == 0:
            return arg.value.strip_code(), False

        def map_author(link):

            text = link.title.strip_code()

            if text and text.endswith(')'):
                text = re.sub(r'^((.*) \(.*?\))$', r'\1|\2', text)

            text = text.replace("Author:", '').replace("author:", '')

            # for portal_hint in ['Parliament, Council, Government, House of']:
            #     for portal_hint in text:
            #         text = 'Portal:' + text
            #         break

            return text

        auths = list(map(map_author, links))
        return auths, True

    def set_author_field(self, item, field, var):
        if var:
            item[field], have_links = self.process_authors(var)

            # if we have links, assume that the nowiki is to deal
            # with them, and we no longer need it
            if have_links and self.nowiki:
                self.nowiki = False

    def process(self, instance):

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

        self.nowiki = instance.get('nowiki', False)

        json_item = {
            'title': title.value.strip_code(),
        }

        self.set_author_field(json_item, 'author', author)
        self.set_author_field(json_item, 'translator', translator)
        self.set_author_field(json_item, 'editor', editor)
        self.set_author_field(json_item, 'illustrator', illustrator)

        if date:
            json_item['year'] = date.value.strip_code()

        if display:
            json_item['display'] = display.value.strip_code()

        if item_type:
            json_item['type'] = item_type.value.strip_code()

        if self.nowiki:
            json_item['nowiki'] = True

        return json_item


class NewTextProcessor():

    def run(self, page, section):

        wikicode = mwparserfromhell.parse(page.text)

        item_name = 'new texts/item'

        data = []

        sections = wikicode.get_sections(matches=section)
        templates = sections[0].filter_templates()

        for instance in [x for x in templates if x.name.strip().lower() == item_name]:
            entry_processor = EntryProcessor()
            json_item = entry_processor.process(instance)

            if json_item:
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

    site = pywikibot.Site(args.lang, 'wikisource')
    page = pywikibot.Page(site, args.page)

    # log_level = logging.DEBUG if args.verbose else logging.INFO
    # logging.basicConfig(level=log_level)

    ntp = NewTextProcessor()
    data = ntp.run(page, args.section)
    s = json.dumps([data], indent=4)
    print(s)


if __name__ == "__main__":
    main()
