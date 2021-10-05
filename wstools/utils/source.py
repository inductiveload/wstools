
import logging
import os
import time
import zipfile

import utils.mime_utils as MIME

import requests
import urllib.parse
import io
import utils.update_bar

module_logger = logging.getLogger('wstools.source')


def dl_img(ofprefix, source, sequence):

    img_data, content_type = source.get_image(sequence)

    if (len(img_data) == 0):
        raise(ValueError("zero-length image data for sequence: {}".format(sequence)))

    ext = MIME.mime_to_ext(content_type)

    ofname = ofprefix + ext

    module_logger.debug("Saving image for seq {} to {}".format(sequence, ofname))

    with open(ofname, "wb") as of:
        of.write(img_data)


def dl_ocr(ofprefix, source, sequence):

    ocr_data = source.get_coord_ocr(sequence)

    ofname = ofprefix + ".hocr"

    module_logger.debug("Saving OCR for seq {} to {}".format(sequence, ofname))

    with open(ofname, "wb") as of:
        of.write(ocr_data)


def have_image_with_prefix(prefix):
    return have_file_with_prefix(prefix, MIME.image_exts())


def have_ocr_with_prefix(prefix):
    return have_file_with_prefix(prefix, [".hocr"])


def have_file_with_prefix(prefix, ext_list):

    for ext in ext_list:
        fn = prefix + ext
        if os.path.exists(fn) and (os.path.getsize(fn) > 0):
            return True

    return False


def dl_to_directory(source, output_dir, skip_existing=True,
                    ocr=True, images=True, make_dirs=True):

    if not os.path.exists(output_dir):
        if make_dirs:
            os.makedirs(output_dir, exist_ok=True)
        else:
            raise ValueError("Directory missing, but make_dirs not set")

    num_pages = source.get_num_pages()

    print(num_pages)

    for i in range(1, num_pages + 1):

        esc_id = sanitise_id(source.get_id())

        ofprefix = os.path.join(output_dir, "{id}.{seq:04d}".format(
                                id=esc_id, seq=i))

        if images:
            if skip_existing and have_image_with_prefix(ofprefix):
                module_logger.debug(
                        "Skipping image for existing seq: {}".format(i))
            else:
                dl_img(ofprefix, source, i)

        if ocr:
            print(ofprefix, have_ocr_with_prefix(ofprefix), skip_existing)
            if skip_existing and have_ocr_with_prefix(ofprefix):
                module_logger.debug(
                        "Skipping OCR for existing seq: {}".format(i))
            else:
                dl_ocr(ofprefix, source, i)
                time.sleep(1)


def extract_zip_to(zip_fo, dir_name):
    with zipfile.ZipFile(zip_fo) as zip_ref:
        zip_ref.extractall(dir_name)


def sanitise_id(id):
    return id.replace('/', '_').replace(':', '_').replace('$', '_')


def get_from_url(url, session=None, name=None):

    if session is None:
        session = requests.Session()

    r = session.get(url, stream=True)
    r.raise_for_status()

    try:
        clen = int(r.headers['Content-Length'])
    except (KeyError, ValueError):
        clen = None

    if not name:
        urlo = urllib.parse.urlparse(url)
        print(urlo, url)

        try:
            name = urlo.path.split['/'][-1]
        except IndexError:
            pass

    buffer = io.BytesIO()

    with utils.update_bar.get_download_bar(name, clen) as bar:
        for data in r.iter_content(chunk_size=1024*1024*1):
            size = buffer.write(data)
            bar.update(size)

    return buffer


class Source():

    def can_download_file(self):
        """
        Can this source provide direct access to files?
        """
        return False

    def normalise_id(self):
        raise NotImplementedError
