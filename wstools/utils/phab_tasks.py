#! /usr/bin/env python3

import requests
import os
import argparse
import logging
import dotenv


PROJECTS = {
    'Wikimedia-Site-Requests': 'PHID-PROJ-gsanzacbtgmvan4hfpih',
    'Commons': 'PHID-PROJ-wxsmdo7s25bucsqb6gir'
}


def post_to_phab(endpoint, data):
    s = requests.Session()
    data['api.token'] = os.getenv('PHAB_API_KEY')

    url = os.getenv('PHAB_BASEURL') + '/api/' + endpoint

    return s.post(url, data=data)


def request_server_side_upload(url, wiki, filename, username, file_desc,
                               t278104=False, extra_projs=[], filesize=None,
                               parent_task=None, extra=None):
    desc = f"""
Please upload the following file to {wiki}:

* URL: {url}
* Filename: {filename}
* Username: {username}

File description:
```
{file_desc}
```
"""

    title = f'Server side upload to {wiki}'

    root, ext = os.path.splitext(filename)

    if filesize:
        title += f' ({filesize // (1024 * 1024)}MB {ext[1:]})'

    if extra:
        desc += "\n\n" + extra

    if t278104:
        desc += "\n\nAPI uploads have repeatedly failed due to T278104"

    projIDs = [
        PROJECTS['Wikimedia-Site-Requests']
    ]

    if wiki == 'commons':
        projIDs.append(PROJECTS['Commons'])

    if extra_projs:
        projIDs += extra_projs

    data = {
        "output": "json"
    }

    def add_transaction(i, dtype, dvalue):
        data[f'transactions[{i}][type]'] = dtype

        if isinstance(dvalue, list):
            li = 0
            for v in dvalue:
                data[f'transactions[{i}][value][{li}]'] = v
                li += 1
        else:
            data[f'transactions[{i}][value]'] = dvalue

    add_transaction(0, "title", title)
    add_transaction(1, "description", desc)
    add_transaction(2, "status", 'open')
    add_transaction(3, "priority", 'triage')


    add_transaction(4, "projects.set", projIDs)

    if parent_task:
        add_transaction(5, 'parent', parent_task)

    req = post_to_phab('maniphest.edit', data)

    req.raise_for_status()
    results = req.json()

    # print(req.content)

    return results


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-f', '--file', required=True,
                        help='The URL to request upload for')
    parser.add_argument('-F', '--filename', required=True,
                        help='Requested filename')
    parser.add_argument('-u', '--username', required=True)
    parser.add_argument('-d', '--desc', required=True)
    parser.add_argument('-w', '--wiki', default='commons',
                        help='The wiki')

    args = parser.parse_args()

    dotenv.load_dotenv()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    with open(args.desc, 'r') as df:
        description = df.read()

    request_server_side_upload(args.file, args.wiki, args.filename,
                               args.username, description, t278104=True)
