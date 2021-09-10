#! /usr/bin/env python3

import argparse
import logging


import pywikibot
from pywikibot import pagegenerators
import mwparserfromhell

import re


MONTHS = {
    'January': 1,
    'February': 2,
    'March': 3,
    'April': 4,
    'May': 5,
    'June': 6,
    'July': 7,
    'August': 8,
    'September': 9,
    'October': 10,
    'November': 11,
    'December': 12,
    'Jan': 1,
    'Feb': 2,
    'Mar': 3,
    'Apr': 4,
    'May': 5,
    'Jun': 6,
    'Jul': 7,
    'Aug': 8,
    'Sep': 9,
    'Sept': 9,
    'Oct': 10,
    'Nov': 11,
    'Dec': 12
}


def to_month(s):
    try:
        m = int(s)
    except ValueError:

        s = s.replace(".", "")

        m = MONTHS[s]

    return m


class Converter():

    def __init__(self, site, template):
        self.template = template

        # self.gen = pywikibot.Page(site, self.template, ns=site.namespaces.TEMPLATE
        #                      ).getReferences(only_template_inclusion=True)

        cat = pywikibot.Category(site, "Pages with script errors")
        self.gen = pagegenerators.CategorizedPageGenerator(cat)

        self.always = False

    def run(self):
        print("Running")
        for page in self.gen:

            print("Page: {}".format(page))

            wikicode = mwparserfromhell.parse(page.text)
            templates = wikicode.filter_templates()

            links = [x for x in templates if x.name.strip().lower() == self.template.lower()]

            # if len(dis) == 0:
            #     page.purge()
            #     print("Purged {}".format(page))
            #     continue
            #     
            print(links)

            for link in links:

                try:
                    # param = link.get('year')
                    param = link.get(4)
                except ValueError:
                    # the template doesn't have this param
                    continue

                s = str(param.value).strip()

                print(s)

                try:
                    y = int(s)
                except ValueError:

                    done = False

                    mdy = re.match(r"^([A-Z][a-z]+\.?),? +(?:(\d+),? +)?(\d{4})\.?$", s)

                    if mdy:
                        link.add('year', mdy.group(3))
                        link.add('month', to_month(mdy.group(1)))

                        if mdy.group(2):
                            link.add('day', mdy.group(2))
                        done = True

                    if not done:
                        dmy = re.match(r"^(\d+),? +([A-Z][a-z]+\.?),? +(\d{4})\.?$", s)

                        if dmy:
                            link.add('year', dmy.group(3))
                            link.add('month', to_month(dmy.group(2)))

                            if dmy.group(1):
                                link.add('day', dmy.group(1))
                            done = True

                try:
                    link.remove(4)
                except ValueError:
                    pass

            new_text = str(wikicode)

            if new_text != page.text:
                pywikibot.showDiff(page.text, new_text)

                if self.always:
                    choice = 'y'
                else:
                    choice = pywikibot.input_choice(
                            'Do you want to accept these changes?',
                            [('Yes', 'y'), ('No', 'n'), ('all', 'a')],
                            default='N')

                if choice == 'y' or choice == 'a':
                    page.text = new_text
                    page.save("Fix misuse of year parameter for complete date in {{{{{}}}}}".format(self.template))


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-t', '--throttle', type=int, default=5,
                        help='Throttle')

    site = pywikibot.Site("en", "wikisource")
    args = parser.parse_args()

    pywikibot.config.put_throttle = args.throttle

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    for t in ['AJS link']:
        c = Converter(site, t)
        c.run()


if __name__ == "__main__":
    main()
