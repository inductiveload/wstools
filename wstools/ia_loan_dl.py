#! /usr/bin/python

import os
import subprocess
import tqdm
import time

outdir = '/tmp/aca'

os.makedirs(outdir, exist_ok=True)

for i in tqdm.tqdm(range(320, 335)):

    outfile = os.path.join(outdir, f'{i:04d}.jpg')
    scale = 2

    url = f'https://ia903405.us.archive.org/BookReader/BookReaderImages.php?zip=/28/items/autobiographyofc0000henn/autobiographyofc0000henn_jp2.zip&file=autobiographyofc0000henn_jp2/autobiographyofc0000henn_{i:04d}.jp2&id=autobiographyofc0000henn&scale={scale}&rotate=0'
    # url = f'https://ia903405.us.archive.org/BookReader/BookReaderPreview.php?id=autobiographyofc0000henn&subPrefix=autobiographyofc0000henn&itemPath=/28/items/autobiographyofc0000henn&server=ia903405.us.archive.org&page=leaf{i}&fail=preview&&scale={scale}&rotate=0'
    ref = f'https://archive.org/details/autobiographyofc0000henn/page/{i}mode/1up'

    print (url)

    cmd = [
        'curl', url,
        '-H', 'User-Agent: Mozilla/5.0 (X11; Linux x86_64; rv:94.0) Gecko/20100101 Firefox/94.0',
        '-H', 'Accept: image/avif,image/webp,*/*',
        '-H', 'Accept-Language: en-US,en;q=0.5',
        '--compressed',
        '-H', 'Referer: ' + ref,
        '-H', 'Connection: keep-alive',
        '-H', 'Cookie: donation-identifier=4a15a4f202d8546dfa08d474cd3c8b85; abtest-identifier=4eedd510fc4c20b3a014f3e22b093f26; logged-in-sig=1659912392%201628376392%20k8xdIFXkPUrdzhYwNNyz%2Fe6n90T2G3w2Ldy4iAUoUPBZ%2Bsh1EYjngzNjz6iDKqNIDo%2Fhahnfbhfq5aQXateu2tt5QkyPsvEVtgC%2FrgFBqIKBVcggI6fhAFdxLA4ZuF8INxXKHTe0SdsCBEraXn3jE22yaHissHeDP1rvMOshzfE%3D; logged-in-user=inductiveload%40gmail.com; collections=bostonpubliclibrary%2Csifieldbooks%2Cbiodiversity; PHPSESSID=frj20s4d312b64c0oi8fv26uu6; br-loan-=1; loan-=1637412535-33c29bf40cd987be6ab64a736b676ee3; br-loan-autobiographyofc0000henn=1; loan-autobiographyofc0000henn=1637447754-dd71f1cd9865a1e81d398fba5861a9f5; ol-auth-url=%2F%2Farchive.org%2Fservices%2Fborrow%2FXXX%3Fmode%3Dauth',
        '-H', 'Sec-Fetch-Dest: image',
        '-H', 'Sec-Fetch-Mode: no-cors',
        '-H', 'Sec-Fetch-Site: same-site',
        '-H', 'Cache-Control: max-age=0',
        '-H', 'TE: trailers',
        '-o', outfile ]

    subprocess.call(cmd)
    time.sleep(1)
