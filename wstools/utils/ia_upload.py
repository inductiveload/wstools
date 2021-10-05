
import internetarchive
import re
import os

import logging


def upload_file(file, filename, title, volume,
    author, editor, date, src_url=None, reupload=False):

    metadata = {
        'mediatype': 'text',
        'title': title,
        'creator': author,
        'date': date
    }

    if src_url:
        metadata['source'] = src_url

    if volume:
        metadata['volume'] = volume

    root, ext = os.path.splitext(filename)

    # slugify
    identifier = re.sub(r'[^A-Za-z0-9\-]', '', root)

    ia_filename = identifier + ext

    filemap = {
        ia_filename: file
    }

    logging.debug(identifier)
    logging.debug(metadata)

    item = internetarchive.get_item(identifier)

    has_file = False
    for f in item.files:

        if f['name'] == ia_filename:
            has_file = True
            break

    if not has_file or reupload:
        item.upload(filemap, metadata=metadata, queue_derive=True)
    else:
        logging.debug(f'File exists: {ia_filename}')

    return identifier, ia_filename
