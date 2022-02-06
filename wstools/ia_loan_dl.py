#! /usr/bin/python

import concurrent.futures
import os

import requests
import tqdm


def download_image(url, headers, outfile):

    r = requests.get(url, headers=headers)
    r.raise_for_status()

    with open(outfile, 'wb') as ofo:
        ofo.write(r.content)


outdir = '/tmp/soc'

os.makedirs(outdir, exist_ok=True)

future_to_index = {}

# params for building the requests
iaid = 'secretofchimneys00agat'
server = 'ia800309'
zipn = 31
scale = 4
cookie = 'donation-identifier=3498ca0f8548ee81b25d5a5167bedaf7; abtest-identifier=8d65ae618465dd0ac020cfe1ca92e144; G_ENABLED_IDPS=google; logged-in-sig=1669114532%201637578532%20NifzTunrJEbwS%2BqdbZc%2FtIXPiLQ5ccKsToabl2lLp%2FUFQsllSQbl8evQTngX%2BGTwyBNQca6pcyY7FECK%2Bu%2BdpaZp%2B7ZcDD0aHnnkTSsM4jXELPwY%2F0dVQHhrABsDulyBy83rQthbfHI9WNL%2B9Kt%2Fm1RaKUxqtWyT8uyA4bJ4Wbw%3D; logged-in-user=inductiveload%40gmail.com; collections=copyrightrecords%2Clendinglibrary%2Copensource%2Cpulpmagazinearchive%2Cpub_all-the-year-round%2Cpub_smart-set%2Camiga-computing-magazine%2Ccommodoremagazines%2Ccomputermagazines%2Cufonewsletters; view-search=tiles; PHPSESSID=edfii9c63hl02hmnqpltkboatj; br-loan-secretofchimneys00agat=1; loan-secretofchimneys00agat=1644188532-b9df6b96374a78adf188d8c5f3aa0849; ol-auth-url=%2F%2Farchive.org%2Fservices%2Fborrow%2FXXX%3Fmode%3Dauth; search-inside-secretofchimneys00chri=1644187979-501b3bf7d69db9fb7b318b3956eae32c'

first_page = 156
last_page = 232

dl_threads = 16

page_iter = range(first_page, last_page + 1)

def download_nth(i):

    outfile = os.path.join(outdir, f'{i:04d}.jpg')

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
