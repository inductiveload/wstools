#! /usr/bin/python

import concurrent.futures
import os

import requests
import tqdm
import internetarchive
import argparse
import logging
from urllib.parse import urlparse


def download_image(url, headers, outfile):

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    with open(outfile, 'wb') as ofo:
        ofo.write(r.content)


def get_server_and_zipn(iaid):

    pdfs = internetarchive.get_files(iaid, formats=["Text PDF"])

    for pdf in pdfs:
        r = requests.get(pdf.url)
        redirected = urlparse(r.url)

        server = redirected.hostname.split('.')[0]
        zipn = redirected.path.split('/')[1]
        break

    return server, zipn

def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-o', '--outdir',
                        help='Output dir')
    parser.add_argument('-i', '--id', required=True,
                        help='IA ID')
    parser.add_argument('-s', '--scale', type=int, default=2,
                        help='Scale')
    parser.add_argument('-f', '--first', type=int, default=1,
                        help='First page')
    parser.add_argument('-l', '--last', type=int, required=True,
                        help='Last page')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    if not args.outdir:
        args.outdir = f'/tmp/{args.id}'

    # params for building the requests
    scale = args.scale
    cookie = 'donation-identifier=3498ca0f8548ee81b25d5a5167bedaf7; abtest-identifier=8d65ae618465dd0ac020cfe1ca92e144; G_ENABLED_IDPS=google; logged-in-sig=1669114532%201637578532%20NifzTunrJEbwS%2BqdbZc%2FtIXPiLQ5ccKsToabl2lLp%2FUFQsllSQbl8evQTngX%2BGTwyBNQca6pcyY7FECK%2Bu%2BdpaZp%2B7ZcDD0aHnnkTSsM4jXELPwY%2F0dVQHhrABsDulyBy83rQthbfHI9WNL%2B9Kt%2Fm1RaKUxqtWyT8uyA4bJ4Wbw%3D; logged-in-user=inductiveload%40gmail.com; collections=copyrightrecords%2Clendinglibrary%2Copensource%2Cpulpmagazinearchive%2Cpub_all-the-year-round%2Cpub_smart-set%2Camiga-computing-magazine%2Ccommodoremagazines%2Ccomputermagazines%2Cufonewsletters; PHPSESSID=utpdl1cdq4j7p8rceifl35ak23; search-inside-thesermonsofthec0000unse=1648068323-71424cfcfdcd612821f28cfebef210b3; br-loan-thesermonsofthec0000unse=1; loan-thesermonsofthec0000unse=1648068743-496003bf0a6c59ce1eb6ca7c88d81bf4; ol-auth-url=%2F%2Farchive.org%2Fservices%2Fborrow%2FXXX%3Fmode%3Dauth'
    first_page = args.first
    last_page = args.last

    os.makedirs(args.outdir, exist_ok=True)

    future_to_index = {}

    server, zipn = get_server_and_zipn(args.id)

    dl_threads = 16

    page_iter = range(first_page, last_page + 1)

    def download_nth(i):
        iaid = args.id
        outfile = os.path.join(args.outdir, f'{i:04d}.jpg')

        url = f'https://{server}.us.archive.org/BookReader/BookReaderImages.php?zip=/{zipn}/items/{iaid}/{iaid}_jp2.zip&file={iaid}_jp2/{iaid}_{i:04d}.jp2&id={iaid}&scale={scale}&rotate=0'
        ref = f'https://archive.org/details/{iaid}/page/{i}mode/1up'

        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:94.0) Gecko/20100101 Firefox/94.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': ref,
            'Connection': 'keep-alive',
            'Cookie': cookie,
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'TE': 'trailers',
        }

        download_image(url, headers, outfile)

    with concurrent.futures.ThreadPoolExecutor(max_workers=dl_threads) as executor:
        with tqdm.tqdm(total=len(page_iter)) as pbar:

            future_to_index = {executor.submit(download_nth, i): i for i in page_iter}

            for future in concurrent.futures.as_completed(future_to_index):
                i = future_to_index[future]
                try:
                    data = future.result()
                except Exception as exc:
                    print('%r generated an exception: %s' % (i, exc))

                pbar.update(1)

if __name__ == "__main__":
    main()
