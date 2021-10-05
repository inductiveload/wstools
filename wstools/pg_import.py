#! /usr/bin/env python3

import argparse
import logging

# import pywikibot

import xml.sax
import re


class Page():

    def __init__(self, num):
        self.content = ''
        self.number = num

    def append(self, t):
        self.content += t


class Footnote():

    def __init__(self, fnid):
        self.fnid = fnid
        self.content = ''


class StreamHandler(xml.sax.handler.ContentHandler):

    def __init__(self):
        self.pages = [
            Page(None)
        ]
        self.footnotes = {}
        self.in_body = False
        self.in_page_num = False

        self.in_footnote = 0
        self.curr_footnote = None

        self.in_footnote_ref = 0

        self.no_output = 0

        self.current_pg_name = ''
        self.curr_page = self.pages[-1]

    def get_pg_num(self, n):

        m = re.match(r'\[([Pp]g\.?|page) (.*?)\.?\]', n)

        if m:
            return m.group(2)
        return n

    def collapse_lines(self, t):

        t = re.sub(r'(?<!-)\n', ' ', t)
        t = re.sub(r'-\n', '', t)
        return t

    def startElement(self, name, attrs):
        self.lastName = name

        if name == 'body':
            self.in_body = True
            return

        if self.no_output > 0:
            self.no_output += 1

        if 'class' in attrs.getNames() and attrs.getValue('class') == 'pagenum':
            self.in_page_num = True
        elif 'class' in attrs.getNames() and attrs.getValue('class') == 'footnotes':
            if self.no_output == 0:
                self.no_output += 1
        elif 'class' in attrs.getNames() and attrs.getValue('class') == 'footnote':
            self.in_footnote = 1

        elif name == 'a' and 'class' in attrs.getNames() and attrs.getValue('class') == 'fnanchor':
            if self.no_output == 0:
                self.no_output += 1

            # leave a replaceable marker for later
            if 'href' in attrs.getNames():
                fnid = re.sub('^#', '', attrs.getValue('href'))
                self.curr_page.append(f'@@fn_ref:{fnid}@@')

        elif self.in_footnote > 0:

            self.in_footnote += 1

            if 'class' in attrs.getNames() and attrs.getValue('class') == 'label':
                self.no_output = True

            # find the ref with the right ID
            if 'id' in attrs.getNames():
                fnid = attrs.getValue('id')
                if fnid.startswith('Footnote'):
                    self.curr_footnote = fnid

        elif name == 'pre':
            if self.no_output == 0:
                self.no_output += 1

        elif name == 'i':
            self.curr_page.append("''")
        elif name == 'b':
            self.curr_page.append("'''")
        # print(name)
        pass

    def endElement(self, name):
        # print("/" + name)

        if self.in_page_num:
            new_pg_num = self.get_pg_num(self.current_pg_name.strip())
            self.curr_page = Page(new_pg_num)
            self.pages.append(self.curr_page)
            self.current_pg_name = ''
            self.in_page_num = False

        if self.no_output > 0:
            self.no_output -= 1

        if self.in_footnote > 0:
            self.in_footnote -= 1

            if self.in_footnote == 0:
                self.curr_footnote = None

        if name == 'i':
            self.curr_page.append("''")
        elif name == 'b':
            self.curr_page.append("'''")
        elif name == 'p' or re.match(r'h\d', name):
            self.curr_page.content = self.curr_page.content.rstrip("\n") + '\n\n'
        elif name == 'body':
            self.in_body = False

    def characters(self, content):

        if self.no_output:
            return

        if self.in_page_num:
            self.current_pg_name += content
        elif self.curr_footnote:
            if self.curr_footnote not in self.footnotes:
                self.footnotes[self.curr_footnote] = Footnote(self.curr_footnote)

            self.footnotes[self.curr_footnote].content += content
        elif self.in_body:
            self.curr_page.content += content


class PageOutput():

    def __init__(self):
        pass

    def map_page(self, n):
        return n

    def output(self, pages, footnotes, index):

        s = ''

        for page in pages:
            pagenum = self.map_page(page.number)
            s += f'\n==__MATCH__:[[Page:{index}/{pagenum}]]==\n'

            def fn_replacer(m):
                fnid = m.group(1)
                fncontent = footnotes[fnid].content.strip()
                return f"<ref>{fncontent}</ref>"

            new_content = re.sub(r"@@fn_ref:(.*?)@@", fn_replacer, page.content)

            new_content = re.sub(r"\n\n+", "\n\n", new_content)

            s += new_content.strip("\n")

            if new_content.endswith("\n\n"):
                s += "\n{{nop}}"

        return s


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--html-file',
                        help='Read from an HTML file')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    parser = xml.sax.make_parser()
    handler = StreamHandler()
    parser.setContentHandler(handler)

    with open(args.html_file) as f:
        parser.parse(f)

    outputter = PageOutput()

    out = outputter.output(handler.pages, handler.footnotes, 'Sandbox.djvu')

    # print(handler.footnotes)
    print(out)


if __name__ == "__main__":
    main()
