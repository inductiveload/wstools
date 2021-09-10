#! /usr/bin/env python3

import argparse
import logging

import pywikibot
import mwparserfromhell

import re


class Mover():

    def __init__(self, target, pages, dry_run):

        self.target = target
        self.pages = pages
        self.dry_run = dry_run
        self.summary_move = "Moving to subpage of [[{}]]".format(target)
        self.summary_edit = "Adjusting header to fit position as subpage".format(target)

        self.delete_edition = True
        self.delete_notes = False

        self.title = "[[../]]"

        self.site = pywikibot.Site('en', 'wikisource')

        self.always = False

    def _tidy_header(self, header):

        for p in header.params:

            p.value = ' ' + p.value.strip() + "\n" + ("" if p.name.strip() == "notes" else " ")
            p.name = ' ' + p.name.strip().ljust(10, ' ')

        header.name = header.name.strip() + "\n "

        print(header)

    def _get_prevnext_target(self, s):
        parts = s.split("|")

        to = None
        skip = False

        if s.startswith('-'):
            skip = True
            parts[0] = parts[0][1:]

        frm = parts[0]

        if len(parts) == 1:
            to = parts[0]
        elif len(parts[1]) == 0:
            to = re.sub(r" *\(.*?\) *$", "", parts[0])
        else:
            to = parts[1]

        return frm, to, skip

    def move(self):

        top_page = pywikibot.Page(self.site, self.target)
        logging.debug(top_page)

        i = -1
        for page in self.pages:
            i += 1
            frm, to, skip = self._get_prevnext_target(page)

            # placeholder
            if skip:
                continue

            f_page = pywikibot.Page(self.site, frm)
            t_pagename = self.target + "/" + to

            print(f_page, t_pagename)

            if f_page.isRedirectPage():

                logging.error("Page is already a redirect")

                if self.skip_redirects:
                    continue

                redir_tgt = f_page.getRedirectTarget().title()
                if redir_tgt != t_pagename:
                    raise ValueError("Redirect doesn't point to the correct page: got {}, expected {}".format(redir_tgt, t_pagename))

                f_page = pywikibot.Page(self.site, t_pagename)
                old_text = f_page.text
            elif f_page.exists():

                if f_page.isDisambig():
                    raise ValueError("Page is disambiguation: {}".format(f_page))

                old_text = f_page.text

                if not self.dry_run:
                    f_page.move(t_pagename, noredirect=False, reason=self.summary_move)
                    f_page = pywikibot.Page(self.site, t_pagename)
                else:
                    logging.info("Moving: {} -> {}".format(f_page, t_pagename))
            else:

                if not self.allow_missing:
                    raise KeyError("Page missing: {}".format(f_page))
                else:
                    continue

            wikicode = mwparserfromhell.parse(f_page.text)
            templates = wikicode.filter_templates()

            def template_finder(node, want):
                return node.name.strip().lower() == want.lower()

            header = [x for x in templates if template_finder(x, 'header')][0]

            if self.delete_edition:

                try:
                    header.remove("edition", keep_field=False)
                except ValueError:
                    pass

            if self.delete_notes:
                header.add('notes', None)

            if self.delete_year:
                try:
                    header.remove('year')
                except ValueError:
                    pass

            try:
                title = header.get('title').value
            except ValueError:
                title = page

            header.add('section', title)
            header.add('title', self.title)

            if i > 0:
                _, pt, _ = self._get_prevnext_target(self.pages[i - 1])
                header.add('previous', "[[../{}/]]".format(pt))

            if i < len(self.pages) - 1:
                _, pn, _ = self._get_prevnext_target(self.pages[i + 1])
                header.add('next', "[[../{}/]]".format(pn))

            self._tidy_header(header)

            new_text = str(wikicode)

            new_text = re.sub(r"}}\s*< *poem *>\s*[ ']*([A-Z-'\"?! ]+?)[' ]*\n\s", r"}}\n\n{{center|\1}}\n\n<poem>\n", new_text)
            new_text = re.sub(r"<poem>", "{{block center/s}}<poem>", new_text)
            new_text = re.sub(r"< */ *poem *>", "</poem>{{block center/e}}", new_text)

            if new_text != old_text:
                pywikibot.showDiff(old_text, new_text)

                if self.always:
                    choice = 'y'
                else:
                    choice = pywikibot.input_choice(
                            'Do you want to accept these changes?',
                            [('Yes', 'y'), ('No', 'n'), ('all', 'a')],
                            default='N')

                if choice == 'y' or choice == 'a':
                    f_page.text = new_text

                    if (self.dry_run):
                        print("Saving (dummy)")
                    else:
                        f_page.save(self.summary_edit)

                    if choice == 'a':
                        self.always = True


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--file',
                        help='File of pages to move')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='Dry run?')
    parser.add_argument('-t', '--throttle', default=5,
                        help='Put throttle')
    parser.add_argument('-a', '--always', action='store_true',
                        help='Always accept')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    # pwbl = logging.getLogger("pywiki")
    # pwbl.disabled = True
    pywikibot.config.put_throttle = args.throttle

    variables = {}
    pages = []

    with open(args.file, 'r') as inf:

        for line in inf:

            line = line.strip()

            if re.match(r"^# *END *#$", line):
                break

            # comment
            if line.startswith("#") or not line:
                continue

            m = re.match(r"^\$([A-Z0-9_-]+)=(.*)$", line)

            if m:
                variables[m.group(1).strip()] = m.group(2).strip()

            else:
                pages.append(line)

    print(variables)
    print(pages)

    m = Mover(variables['PREFIX'], pages, args.dry_run)

    def get_var(v):

        try:
            return variables[v]
        except KeyError:
            pass

        return None

    m.delete_edition = True
    m.delete_notes = get_var('DELETE_NOTES') == '1'
    m.delete_year = get_var('DELETE_YEAR') in ['1', None]
    m.skip_redirects = True
    m.always = args.always

    m.allow_missing = True

    m.move()


if __name__ == "__main__":
    main()
