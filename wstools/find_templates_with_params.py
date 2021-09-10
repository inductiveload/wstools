#! /usr/bin/env python3

import argparse
import logging


import pywikibot
import mwparserfromhell

import requests_cache

PAGE_NS = 104


class TemplateProcessor():

    def __init__(self, page, template, param_to_get):
        self.page = page
        self.template = template
        self.param_to_get = param_to_get

        self.template_name = template.lower().replace("template:", "")

        self.print_every_page = False

    def __iter__(self):
        return self

    def __next__(self):

        if self.print_every_page:
            print(self.page.title())

        wikicode = mwparserfromhell.parse(self.page.text)
        templates = wikicode.filter_templates()

        for instance in [x for x in templates if x.name.strip().lower() == self.template_name]:

            try:
                param = instance.get(self.param_to_get)
            except ValueError:
                # the template doesn't have this param
                continue

            return self.page, wikicode, instance, param

        raise StopIteration


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-p', '--param', required=True,
                        help='The parameter')
    parser.add_argument('-t', '--template', required=True,
                        help='The template')
    parser.add_argument('-o', '--output-file',
                        help='OF')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO

    logging.getLogger("pywiki").setLevel(pywikibot.logging.ERROR)

    pwbl = logging.getLogger("pywiki")
    pwbl.disabled = True

    logging.basicConfig(level=log_level)

    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests_oauthlib").setLevel(logging.WARNING)
    logging.getLogger("oauthlib.oauth1.rfc5849").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    requests_cache.install_cache('findtemplates')

    logging.debug("Finding {{{{{}}}}}".format(args.template))

    site = pywikibot.Site("en", "wikisource")

    of = None
    if args.output_file:
        logging.debug("Open output file")
        of = open(args.output_file, "w")

    try:
        param = int(args.param)
    except ValueError:
        param = args.param

    mytpl = site.namespaces.TEMPLATE
    gen = pywikibot.Page(site, args.template, ns=mytpl).getReferences(
                only_template_inclusion=True)

    count = 0

    for page in gen:

        tproccesor = TemplateProcessor(page, args.template, args.param)

        for page, wikicode, inst, param in tproccesor:

            # print(page, inst, param)
            # print(page.name)

            count += 1

            # param.value = "5675"

            # # print(inst)
            # print(str(wikicode))

            logging.debug(page.name + "\t" + str(param.value).strip())

            if of is not None:
                of.write(page.name + "\t" + str(param.value).strip() + "\n")

    logging.debug("Found: {} pages".format(count))


if __name__ == "__main__":
    main()
