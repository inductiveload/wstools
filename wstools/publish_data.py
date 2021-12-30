#! /usr/bin/env python3

import argparse
import logging

import json
import luadata
import os

import pywikibot


def get_comment(text):

    in_block = False

    comment = ''

    for line in text.split("\n"):
        if not in_block and not line.lstrip().startswith('--'):
            break
        if line.startswith('--[=['):
            in_block = True
            comment += line + '\n'
        elif in_block and ']=]' in line:
            in_block = False
            comment += line.split(']=]')[0] + ']=]' + '\n'
            break
        else:
            comment += line + '\n'

    return comment


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='count', default=0,
                        help='show debugging information')
    parser.add_argument('-i', '--input',
                        help='The input file (JSON or Lua)')
    parser.add_argument('-o', '--output',
                        help='The ouput page - Lua format if in Module, else .json')
    parser.add_argument('-f', '--force', action='store_true',
                        help='Save without asking')
    parser.add_argument('-n', '--dry-run', action='store_true',
                        help='Do not actually save the page')
    parser.add_argument('-s', '--summary',
                        help='Summary to use')

    args = parser.parse_args()

    site = pywikibot.Site()
    tgt_page = pywikibot.Page(site, args.output)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    pywikibot.config.put_throttle = 0

    if not os.path.isfile(args.input):
        raise ValueError(f'Not a file: {args.input}')

    if args.summary is None:
        args.summary = "Updating data"

    _, ext = os.path.splitext(args.input)

    with open(args.input, 'r') as ifo:
        if (ext.lower() in '.json'):

            try:
                data = json.loads(ifo.read())
            except json.decoder.JSONDecodeError:
                logging.error("JSON decode error:")
                raise

        elif (ext.lower() in '.lua'):
            data = luadata.unserialize(ifo, encoding="utf-8", multival=False)
        else:
            raise ValueError(f'Unknown input format type: {ext}')

    cm = tgt_page.content_model
    old_text = tgt_page.text

    if cm == 'Scribunto':
        formatted = luadata.serialize(data, encoding='utf=8', indent='\t',
                                      indent_level=0)
        # convert to a return-data module
        new_text = get_comment(old_text) + 'return ' + formatted
    else:
        formatted = json.dumps(data)
        new_text = formatted

    if new_text == old_text:
        logging.info("Page not changed.")
    else:
        if not args.force:
            pywikibot.showDiff(old_text, new_text)

            choice = pywikibot.input_choice(
                    'Do you want to accept these changes?',
                    [('Yes', 'y'), ('No', 'n')],
                    default='N')

            if choice == 'y':
                tgt_page.text = new_text

            if (args.dry_run):
                print("Dry run: would be saving {tgt_page}")
            else:
                tgt_page.save(args.summary)


if __name__ == "__main__":
    main()
