#! /usr/bin/env python3

import argparse
import logging


import pywikibot
from pywikibot import pagegenerators
import mwparserfromhell

import re


class Converter():

    def __init__(self, site, templates):
        self.templates = templates

        # self.gen = pywikibot.Page(site, self.template, ns=site.namespaces.TEMPLATE
        #                      ).getReferences(only_template_inclusion=True)

        cat = pywikibot.Category(site, "Dropinitials with image in parameter 1")
        self.gen = pagegenerators.CategorizedPageGenerator(cat)

        self.guess_from_image_name = False

        self.always = False
        self.purge_others = False

    def get_img(self, s):

        m = re.search(r"(File:|Image:|Media:)([^\]|]*)", s, flags=re.I)

        if not m:
            return None

        if "overfloat" in s:
            return None

        image = m.group(2)

        m = re.search(r"(?:alt *= *([^\|\]]+)|\|([A-Z])[\|\]])", s)

        if self.guess_from_image_name:
            if not m:
                m = re.search(r"(?:[Ll]etter|[Ii]lluminated|_|\b)([A-Za-z])\b", image)

        if m:
            alt = m.group(1) if m.group(1) else m.group(2)
            alt = alt.upper()
        else:
            alt = None

        # skip upright sizing for now
        if re.search(r"upright *=", s):
            return None

        m = re.search(r"\| *([0-9]+px) *[|\]]", s)

        if m:
            size = m.group(1)
        elif "frameless" in s:
            size = "220px"
        else:
            size = None

        return [image, alt, size]

    def run(self):
        for page in self.gen:

            wikicode = mwparserfromhell.parse(page.text)
            templates = wikicode.filter_templates()

            dis = [x for x in templates if x.name.strip().lower() in self.templates]

            if len(dis) == 0 and self.purge_others:
                page.purge(forcerecursivelinkupdate=True)
                print("Purged {}".format(page))
                continue

            for di in dis:

                try:
                    param = di.get(1)
                except ValueError:
                    # the template doesn't have this param
                    continue

                s = str(param.value)

                if not s.startswith("[[") and s.endswith("]]"):
                    continue

                print(param.value)
                img = self.get_img(s)

                if not img:
                    continue

                print(img)

                if not img[1]:

                    try:
                        img[1] = di.get('alt').value
                        print(img[1])
                    except ValueError:
                        pass

                if not img[1] and not self.always:
                    print(wikicode)
                    img[1] = pywikibot.input("Enter alt text")

                di.add(1, img[1])
                di.add('image', img[0])

                if img[2]:
                    di.add('imgsize', img[2])

                try:
                    di.remove(2)
                except ValueError:
                    pass

                try:
                    di.remove('alt')
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
                    page.save("Use the image parameter of {{{{{}}}}} over direct image wikicode".format(self.templates[0]))

                    if choice == 'a':
                        self.always = True


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-t', '--throttle', type=int, default=5,
                        help='Throttle')
    parser.add_argument('-g', '--guess', action='store_true',
                        help='Guess letters')
    parser.add_argument('-a', '--always', action='store_true',
                        help='Always make edit')
    parser.add_argument('-p', '--purge', action='store_true',
                        help='Purge pages without templates')

    site = pywikibot.Site("en", "wikisource")
    args = parser.parse_args()

    pywikibot.config.put_throttle = args.throttle

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    for t in [['dropinitial', 'drop initial', 'di', 'dropcap', 'drop capital'], ['largeinitial']]:
        c = Converter(site, t)

        c.guess_from_image_name = args.guess
        c.always = args.always
        c.purge_others = args.purge
        c.run()


if __name__ == "__main__":
    main()
