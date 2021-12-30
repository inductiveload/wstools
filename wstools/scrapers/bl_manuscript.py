#! /usr/bin/env python3

import argparse
import logging

import requests
import lxml.html
import lxml.etree
import subprocess
import os
import tqdm
import dotenv


class BLMScraper():

  def __init__(self) -> None:
      self.session = requests.Session()
      headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:95.0) Gecko/20100101 Firefox/95.0'
      }
      self.session.headers.update(headers)

  def get_pagelist(self, id):

    url = f'https://www.bl.uk/manuscripts/Viewer.aspx?ref={id}'

    r = self.session.get(url)
    r.raise_for_status()

    doc = lxml.html.fromstring(r.content)

    pl_elem = doc.get_element_by_id('PageList')

    values = pl_elem.attrib['value'].split('||')

    values = [v for v in values if v != '##']

    return values

  def get_dzi_url(self, pgid):

    return f'https://www.bl.uk/manuscripts/Proxy.ashx?view={pgid}.xml'

  def dezoomify(self, pgid, outfile):
    dzi = self.get_dzi_url(pgid)

    bin = os.getenv('DEZOOMIFY_PATH')
    if not bin:
      bin = 'dezoomify-rs'

    command = [
      bin,
      '-l',
      dzi,
      outfile
    ]

    subprocess.check_call(command)

  def get(self, id, outdir):

    os.makedirs(outdir, exist_ok=True)

    pages = self.get_pagelist(id)
    keep_existing = True

    i = 0
    for pgid in tqdm.tqdm(pages):
      i += 1
      pfn = os.path.join(outdir, f'{i:04d}.jpg')

      if os.path.exists(pfn):
        if keep_existing and os.path.getsize(pfn) > 0:
          continue
        else:
          # dz-rs can't handle existing files
          os.remove(pfn)

      self.dezoomify(pgid, pfn)

def main():

  dotenv.load_dotenv()

  parser = argparse.ArgumentParser(description='')
  parser.add_argument('-v', '--verbose', action='count', default=0,
            help='show debugging information')
  parser.add_argument('-i', '--id', required=True,
                      help="Document ID (including a ")
  parser.add_argument('-o', '--outdir')

  args = parser.parse_args()

  log_level = logging.DEBUG if args.verbose else logging.INFO
  logging.basicConfig(level=log_level)

  if not args.outdir:
    basedir = os.getenv('WSTOOLS_OUTDIR')
    if basedir:
      args.outdir = os.path.join(basedir, args.id)

  if not args.outdir:
    raise ValueError('No output dir specfified')

  scraper = BLMScraper()

  scraper.get(args.id, args.outdir)

if __name__ == '__main__':
  main()