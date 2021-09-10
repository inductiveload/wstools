#! /usr/bin/env python3

import argparse
import logging

import pywikibot
from pywikibot import pagegenerators
import mwparserfromhell
import re


class LargeImgReplaceBot(
        pywikibot.bot.SingleSiteBot,
        pywikibot.bot.ExistingPageBot):

    def __init__(self, generator, **kwargs):
        # call initializer of the super class
        super().__init__(site=True, **kwargs)
        # assign the generator to the bot
        self.generator = generator

    def treat_page(self):

        print(self.current_page.namespace)

        original_text = self.current_page.text
        wikicode = mwparserfromhell.parse(self.current_page.text)

        templates = wikicode.filter_templates()

        for t in [t for t in templates if t.name == "large image"]:
            try:
                img = t.get(1)
            except ValueError:
                img = t.get("file")

            links = img.value.ifilter_wikilinks()

            morethanone = False

            for link in links:

                if morethanone:
                    raise(IndexError)

                parts = link.text.split("|")

                size = [p for p in parts if re.match("[0-9]+px", p.strip())]

                if not len(size):
                    raise ValueError("no size found")
                size = size[0]

                morethanone = True

            if t.has("max-width") and t.get("max-width").value != "100%":
                max_width = size
                size = t.get("max-width").value
            else:
                max_width = None

            file = re.sub("^[fF]ile:", "", link.title.strip_code())

            new_t = """{{{{FI
 | file     = {fn}
 | width    = {sz}""".format(fn=file, sz=size)

            if max_width is not None:
                new_t += "\n | imgwidth = " + max_width

            try:
                style = t.get("style").value
                new_t += "\n | cstyle   = {}".format(style)
            except ValueError:
                pass

            new_t += "\n}}"

            wikicode.replace(t, new_t)

        # print(wikicode)
        # 
        pywikibot.showDiff(original_text, wikicode, context=1)

        summary = "Convert {{large image}} to {{FI}}, now that {{FI}} doesn't load enourmous images"
        self.put_current(wikicode, summary=summary, show_diff=True)


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--pages',
                        help='List of pages')
    args = parser.parse_args()

    # log_level = logging.DEBUG if args.verbose else logging.INFO
    # logging.basicConfig(level=log_level)

    # pwbl = logging.getLogger("pywiki")
    # pwbl.disabled = True

    site = pywikibot.Site('en', "wikisource")

    tmpl_page = pywikibot.Page(site, "template:large image")
    ref_gen = tmpl_page.getReferences()

    gf = pagegenerators.GeneratorFactory(site)
    gf.handleArg("-namespace:Page")

    gen = gf.getCombinedGenerator(ref_gen)

    bot = LargeImgReplaceBot(gen)
    bot.run()  # guess what it does


if __name__ == "__main__":
    main()