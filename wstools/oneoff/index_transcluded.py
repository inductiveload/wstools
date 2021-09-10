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

    def __init__(self, site):

        self.template = "Index transcluded"
        self.index_template = ":Mediawiki:Proofreadpage_index_template"

        self.gen = pywikibot.Page(site, self.template, ns=site.namespaces.TEMPLATE
                                  ).getReferences(only_template_inclusion=True)

        # cat = pywikibot.Category(site, "Pages with script errors")
        # self.gen = pagegenerators.CategorizedPageGenerator(cat)

        self.always = False

    def get_param(self, t, param_names):

        for n in param_names:
            try:
                return t.get(n).value.strip()
            except ValueError:
                pass

        return None

    def run(self):
        print("Running")
        for page in self.gen:

            print("Page: {}".format(page))

            wikicode = mwparserfromhell.parse(page.text)
            templates = wikicode.filter_templates()

            it = [x for x in templates if x.name.strip().lower() == 'index transcluded']
            ivd = [x for x in templates if x.name.strip().lower() == 'index validated date']

            idx_t = [x for x in templates if x.name.strip().lower() == self.index_template.lower()]

            # print(it, ivd, idx_t)
            #
            if len(idx_t) != 1:
                continue

            # rm redundant
            if len(it) == 1 and len(ivd) == 1:

                s1 = self.get_param(it[0], ['transcluded', 1])
                s2 = self.get_param(ivd[0], ['transcluded', 2])

                if s1 != s2:
                    continue

                wikicode.remove(it[0])
                it = it[1:]

            if (len(it) + len(ivd) != 1):
                continue

            if len(it):

                status = self.get_param(it[0], ['transcluded', 1])
                date = None

                wikicode.remove(it[0])

            else:
                print("Processing IVD")
                status = self.get_param(ivd[0], ['transcluded', 2])
                date = self.get_param(ivd[0], [1])

                wikicode.remove(ivd[0])

            idx_t = idx_t[0]

            print(status, date)

            if status is None:
                status = 'no'

            if status not in ['yes', 'no', 'notadv', 'notimg', 'held']:
                continue

            if status == 'no':
                status = 'check'

            idx_t.add("Transclusion", status)

            if date:
                idx_t.add("Validation_date", date)

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

                    try:
                        page.save("Transfer {{{{[[Template:{}|{}]]}}}} to {} template".format(self.template, self.template, self.index_template))
                    except:
                        print("ERROR")

                if not self.always and choice == 'a':
                    self.always = True


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

    c = Converter(site)
    c.run()


if __name__ == "__main__":
    main()
