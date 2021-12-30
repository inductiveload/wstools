#! /usr/bin/env python3
# A hacky script to convert a directory of images into an OCR'd DJVU file

import argparse
import logging


import os
import shutil
import multiprocessing
import concurrent.futures
import subprocess
import traceback
import re

import sexpdata
import tempfile

import utils.djvu_utils as DJVU
import utils.tiff_utils as TIFF
import utils.file_utils
import utils.range_selection


from html.parser import HTMLParser
from tqdm import tqdm


def get_hocr_bbox(e, pg_bbox=None):

    title = e.attrib['title']

    parts = [x.split()[1:] for x in title.split(";") if x.strip().startswith("bbox ")]

    try:
        box = [int(x) for x in parts[0]]

        if pg_bbox is not None:
            n3 = pg_bbox[3] - box[1]
            n1 = pg_bbox[3] - box[3]

            box[1] = min(n1, n3)
            box[3] = max(n1, n3)
    except KeyError:
        return None

    # zero-sized bbox
    if box[1] == box[3] or box[0] == box[2]:
        return None

    return box


class HocrToSexpParser(HTMLParser):

    def __init__(self):
        super().__init__()
        self.data = None
        self.tag_stack = []

        self.pg_bbox = None

        self.str = ""

    def _get_attr(self, attrs, name):
        for a in attrs:
            if a[0] == name:
                return a
        return None

    def _class_in(self, cands, lst):

        for c in lst:
            if c in cands:
                return True
        return False

    def _get_classes(self, attrs):

        class_a = self._get_attr(attrs, "class")

        if class_a:
            return class_a[1].split()

        return []

    def _get_bbox(self, attrs):

        title_a = self._get_attr(attrs, "title")

        if title_a is not None:
            parts = title_a[1].split(";")

            try:
                bbox = [x.strip() for x in parts if x.lstrip().startswith("bbox")][0]
            except IndexError:
                return None

            bbox = [int(x) for x in bbox.split()[1:]]

            n1 = bbox[1]
            n3 = bbox[3]

            # relative to page
            if self.pg_bbox is not None:
                n1 = self.pg_bbox[3] - n1
                n3 = self.pg_bbox[3] - n3

            # ensure normalised
            bbox[1] = min(n1, n3)
            bbox[3] = max(n1, n3)

            return bbox

        return None

    def handle_starttag(self, tag, attrs):
        # print("Encountered a start tag:", tag, attrs)

        data = {}
        self.tag_stack.append((tag, attrs, data))

        classes = self._get_classes(attrs)

        bbox = self._get_bbox(attrs)

        if "ocr_page" in classes:
            data['type'] = "page"
            data['obj'] = [sexpdata.Symbol("page")] + bbox
            self.pg_bbox = bbox
        elif self._class_in(classes, ["ocr_carea", "ocrx_block"]):
            data['type'] = "area"
            data['obj'] = [sexpdata.Symbol("column")] + bbox
        elif "ocr_par" in classes:
            data['type'] = "para"
            data['obj'] = [sexpdata.Symbol("para")] + bbox
        elif self._class_in(classes, ["ocr_line", "ocr_caption", "ocr_header", "ocr_textfloat"]):
            data['type'] = "line"
            data['obj'] = [sexpdata.Symbol("line")] + bbox
        elif "ocrx_word" in classes:
            data['type'] = "word"
            data['obj'] = [sexpdata.Symbol("word")] + bbox
        else:
            data['type'] = None
            data['obj'] = []

    def handle_endtag(self, tag):
        # print("Encountered an end tag :", tag)

        tag, attr, data = self.tag_stack.pop()

        # append the object to the top of the stack
        if len(self.tag_stack) and data['type'] is not None and len(data['obj']) > 5:
            self.tag_stack[-1][2]['obj'].append(data['obj'])

        if data['type'] == "page":
            logging.debug("Finalised HOCR page")

            if len(data['obj']) > 5:
                self.data = data['obj']

        if data['type'] == "line":
            self.str += "\n"
        elif data['type'] == "para":
            self.str += "\n"

    def handle_data(self, data):
        # print("Encountered some data  :", data)

        if len(self.tag_stack) and self.tag_stack[-1][2]['type'] == "word":
            wrd = data.strip()

            if wrd:
                self.tag_stack[-1][2]['obj'].append(wrd)

            if self.str and not self.str.endswith("\n"):
                self.str += " "
            self.str += wrd


def stream_hocr_to_sexp(hocr):

    parser = HocrToSexpParser()
    parser.feed(hocr)

    if parser.data is not None:
        sexpr_data = sexpdata.dumps(parser.data)
        # logging.debug(sexpr_data)
    else:
        sexpr_data = None

    # print(sexpr_daa)

    return sexpr_data, parser.str


def get_dir_list_with_exts(d, want_exts):

    def want(f):
        _, ext = os.path.splitext(f)
        return os.path.isfile(f) and ext.lower() in want_exts

    files = [os.path.join(d, f) for f in os.listdir(d) if want(os.path.join(d, f))]

    files.sort()

    return files


def im_generic_convert(src, dst):

    logging.debug("IM Conversion {} -> {}".format(src, dst))
    cmd = ["convert", src, dst]
    subprocess.call(cmd)


def convert_img(src, dst):

    _, src_ext = os.path.splitext(src)
    _, dst_ext = os.path.splitext(dst)

    if dst_ext == src_ext:
        # nothing to convert
        pass
    elif src_ext in [".jp2", ".png", ".tif", ".tiff"] and dst_ext in \
            [".jpg", ".jpeg", ".pnm", ".pbm"]:
        im_generic_convert(src, dst)


def convert_img_ocr(src, dst, params):

    cmd = ['convert', src,
           '-alpha', 'off',
           '-normalize',
           '-threshold', f'{params["ocr_threshold"]}%']

    if 'ocr_shave' in params and params['ocr_shave'] is not None:
        # add a white border over the image edges
        cmd += ["-write", "mpr:img0",
                # white BG
                "-evaluate", "set", "100%",
                # reduce centre
                "(", "mpr:img0", "-shave", params["ocr_shave"], ")",
                "-gravity", "center", "-composite"
                ]

    cmd.append(dst)

    logging.debug(cmd)

    subprocess.call(cmd)


def make_djvu_page(src, djvu, max_size):

    logging.debug("Making DJVU page {} -> {}".format(src, djvu))

    _, src_ext = os.path.splitext(src)

    if src_ext in [".jpg", ".jpeg", ".pnm"]:
        cmd = ["c44"]

        if max_size is not None:
            cmd += ["-size", str(max_size)]

        cmd += [src, djvu]
    elif src_ext in [".pbm", ".tiff", ".tif"]:
        cmd = ["cjb2"]

        cmd += [src, djvu]
    else:
        raise RuntimeError("Can't convert {} -> {}".format(src, djvu))

    subprocess.call(cmd)


def do_ocr(src, dest, params):

    logging.debug("OCR {} -> {}".format(src, dest))

    if dest.endswith(".hocr"):
        output_ne = dest[:-len(".hocr")]

    cmd = ["tesseract", src, output_ne, "-l", "+".join(params['ocr_langs'])]

    if "ocr_char_blacklist" in params and params["ocr_char_blacklist"]:
        cmd += ["-c", "tessedit_char_blacklist=" + params["ocr_char_blacklist"]]

    cmd.append("hocr")
    cmd.append("quiet")

    # restrict each tesseract call to a single thread
    env = {"OMP_THREAD_LIMIT": "1"}

    logging.debug(cmd)

    subprocess.call(cmd, env=env)


def insert_hocr_to_djvu(hocr, djvu, text_file):

    logging.debug("Merging OCR to DJVUs")

    with open(hocr, "r") as infile:
        sexpr_text, text = stream_hocr_to_sexp(infile.read())

    if sexpr_text is not None:

        with open(text_file, "w") as ofile:
            ofile.write(text)

        set_page_djvu_ocr(djvu, sexpr_text)
    else:
        logging.debug("No OCR text from: {}".format(hocr))


def set_page_djvu_ocr(djvu_page, sexpr_text):

    logging.debug("Inserting OCR into " + djvu_page)

    cmd = ["djvused", djvu_page, "-e", "select 1; remove-txt", "-s"]
    subprocess.call(cmd)

    with tempfile.NamedTemporaryFile(mode="w") as sexp_f:

        sexp_f.write(sexpr_text)
        sexp_f.flush()

        cmd = ["djvused", djvu_page,
               "-e", f"select 1; set-txt {sexp_f.name}", "-s"]
        logging.debug(cmd)
        subprocess.call(cmd)


def file_exists_nonzero(hocr_fn):
    return os.path.exists(hocr_fn) and os.path.getsize(hocr_fn) > 0

def file_is_in_dir(path, dir):
    head, _ = os.path.split(path)
    return head == dir

def process_page(img, tempdir, params):

    root, ext = os.path.splitext(img)
    head, tail = os.path.split(img)

    dest_root = os.path.join(tempdir, tail)

    logging.debug("Processing {}".format(img))

    conv_info = {
        "origimg": img,
        "orighocr": None,
        "djvu": dest_root + ".djvu",
        "hocr": dest_root + ".hocr",
        "ocrsrc": None,
        "ocr_text": dest_root + ".ocr.txt",
    }

    if ext in ['.jpg', '.jpeg', '.pbm']:
        # do nothing
        conv_info['djvusrc'] = img
    elif ext in ['.pbm']:
        # directly use bitonal for OCR
        conv_info['djvusrc'] = img
        conv_info['ocrsrc'] = img
    elif ext in [".jp2"]:
        # convert to JPG
        conv_info['djvusrc'] = dest_root + ".jpg"
    elif ext in [".png"]:
        if ext in params['bitonal_fmts']:
            conv_info['djvusrc'] = dest_root + ".pbm"
        else:
            # PNM is really, really big and we're going to compress it to death anyway
            conv_info['djvusrc'] = dest_root + ".jpg"

    elif ext in [".tiff", ".tif"]:
        bps = TIFF.get_bitdepth(img)

        if bps == 1:
            # image already bitonal
            conv_info['djvusrc'] = img

        elif ext in params['bitonal_fmts']:
            # colour but we want it bitonal
            conv_info['djvusrc'] = dest_root + ".pbm"
        else:
            # colour, and we want it colour
            conv_info['djvusrc'] = dest_root + ".jpg"
    else:
        RuntimeError("Unsupported file " + img)

    # see if we have original OCR
    exist_hocr = root + ".hocr"
    if os.path.isfile(exist_hocr) and os.path.getsize(exist_hocr) > 0:
        conv_info['orighocr'] = exist_hocr

    # first, make the djvu src file
    if img != conv_info['djvusrc']:
        if (not os.path.exists(conv_info['djvusrc']) or not params['skip_convert']):
            convert_img(img, conv_info['djvusrc'])

    # then make the djvu
    if (not os.path.exists(conv_info['djvu']) or not params['skip_convert']):
        make_djvu_page(conv_info["djvusrc"],
                       conv_info["djvu"],
                       params["max_page_size"])

    if not params["skip_ocr"]:

        hocr_fn = conv_info['hocr']

        if params["use_existing_ocr"] and conv_info['orighocr']:

            logging.debug(f'Using existing HOCR: {conv_info["orighocr"]}')
            hocr_fn = conv_info['orighocr']

        elif params['keep_ocr'] and file_exists_nonzero(hocr_fn):
            logging.debug(
                    f"OCR HOCR file exists, skipping creation of: {hocr_fn}")
        else:

            ocr_src_fn = conv_info['ocrsrc']

            if (params['keep_ocr'] and ocr_src_fn is not None and
                    file_exists_nonzero(ocr_src_fn)):
                logging.debug("OCR source file exists, "
                              f"skipping conversion: {ocr_src_fn}")

            # check the image isn't one of the other conversions
            elif ocr_src_fn not in [conv_info['djvusrc'], img]:
                conv_info["ocrsrc"] = dest_root + ".ocr.png"
                convert_img_ocr(img, conv_info["ocrsrc"], params)

            # then do the OCR on the OCR source file
            do_ocr(conv_info['ocrsrc'], hocr_fn, params)

        insert_hocr_to_djvu(hocr_fn, conv_info["djvu"], conv_info["ocr_text"])

    def tidy_temp_file(key):
        if key in conv_info and conv_info[key] and file_is_in_dir(conv_info[key], tempdir):
            os.remove(conv_info[key])

    if not params['keep_temp']:
        # converted image files take quite a bit of space, which might be
        # on a RAM disk, so tidy them up as we go
        tidy_temp_file('djvusrc')
        tidy_temp_file('ocrsrc')

    return conv_info


def convert_pages(files, tempdir, params):

    page_data = []

    with tqdm(total=len(files), desc='Conv.') as progress_bar:

        with concurrent.futures.ThreadPoolExecutor(
                max_workers=params['threads']) as executor:

            futures = []
            for f in files:

                for excl_regex in params['excl_patterns']:
                    if excl_regex.match(f):
                        logging.debug(
                            f'Skipping file {f} '
                            f'(due to pattern \'{excl_regex.pattern}\')')
                        continue

                futures.append(
                        executor.submit(process_page, f, tempdir, params))

            logging.debug("Image Conversions submitted")

            try:
                for future in concurrent.futures.as_completed(futures):
                    try:
                        data = future.result()
                        logging.debug(
                                f'Conversion complete: {data["origimg"]}')
                        page_data.append(data)
                        progress_bar.update(1)
                    except Exception as exc:
                        print('%r generated an exception: %s' % (future, exc))
                        traceback.print_exc()
                        raise
            except Exception:

                executor.shutdown(wait=False)
                logging.error("Conversions terminating")

                for f in futures:
                    f.cancel()

                return None

            logging.debug("Image Conversions complete")

    return page_data


def main():

    parser = argparse.ArgumentParser(description='')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='show debugging information')
    parser.add_argument('-i', '--in-dir', required=True,
                        help='Image directory')
    parser.add_argument('-2', '--jp2-only', action="store_true",
                        help='Exit after JP2 conversion (if any)')
    parser.add_argument('-C', '--skip-convert', action="store_true",
                        help='Skip image conversion')
    parser.add_argument('-O', '--skip-ocr', action="store_true",
                        help='Skip OCR conversion')
    parser.add_argument('-R', '--ignore-original-ocr', action="store_true",
                        help='Do not use original source OCR even if it exists')
    parser.add_argument('-k', '--keep_ocr', action='store_true',
                        help='Don\'t run OCR if file exists')
    parser.add_argument('-t', '--tempdir',
                        help='The working directory, if not given a temp dir is created')
    parser.add_argument('-D', '--keep-temp', action='store_true',
                        help='Keep temp files and directory when done')
    parser.add_argument('-o', '--out-djvu',
                        help='The output file, if not given, it goes next to the input dir')
    parser.add_argument('-s', '--djvu-size', type=int,
                        help='The output file max size in MB (not guaranteed)')
    parser.add_argument('-b', '--bitonal-formats', default=[], nargs="+",
                        help='List of bitonal formats (e.g. \'.png .tiff\'')
    parser.add_argument('-H', '--ocr-threshold', type=int, default=50,
                        help='OCR binarisation threshold from 0 to 100, default=50. Higher makes the page blacker.')
    parser.add_argument('-c', '--ocr_crop', type=str,
                        help='Crop to use before the OCR step (e.g. 50x80)')
    parser.add_argument('-B', '--ocr_blacklist', default="¢«»<>®©™`¬¥€",
                        help='Blacklisted OCR characters')
    parser.add_argument('-l', '--ocr_langs', nargs="+", default=["eng"],
                        help='OCR language(s)')
    parser.add_argument('-T', '--threads', type=int, default=0,
                        help='Threads to use, 0 for number of cores')
    parser.add_argument('-P', '--exclude-pages', nargs='+', default=[],
                        help='Page to exclude from the output (automatically creates exclusion patterns)')
    parser.add_argument('-X', '--exclusion-patterns', nargs='+', default=[],
                        help='Files to exclude from the output, as regex patterns. More flexible than -P.')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level)

    args.in_dir = os.path.normpath(args.in_dir)
    in_tail = os.path.basename(os.path.normpath(args.in_dir))

    if args.tempdir is None:
        tempdir = os.path.join(tempfile.gettempdir(), "make_doc_tmp_" + in_tail)
    else:
        tempdir = os.path.join(args.tempdir, in_tail)

    os.makedirs(tempdir, exist_ok=True)

    # some folders, e.g. when extracted from ZIPs or TARs have a single
    # directory rather than making it complicated for the caller, spot this
    # and go inside
    args.in_dir = utils.file_utils.skip_interposed_directory(args.in_dir)

    if args.out_djvu is None:
        args.out_djvu = args.in_dir + ".djvu"

    files = get_dir_list_with_exts(args.in_dir, utils.file_utils.get_image_exts())

    if args.djvu_size:
        # in bytes
        max_page_size = (args.djvu_size * 1024 * 1024) // len(files)
    else:
        max_page_size = None

    if args.ocr_threshold < 0 or args.ocr_threshold > 100:
        raise ValueError("OCR threshold {} is not in the range 0-100".format(args.threshold))

    excl_patterns = [re.compile(x) for x in args.exclusion_patterns]

    # add the page exclusions
    for ex_page in utils.range_selection.get_range_selection(args.exclude_pages):
        patt = fr'\b{ex_page:04}\.'
        excl_patterns.append(patt)

    params = {
        "max_page_size": max_page_size,
        "bitonal_fmts": args.bitonal_formats,
        "threads": args.threads if args.threads > 0 else multiprocessing.cpu_count(),
        "keep_ocr": args.keep_ocr,
        "skip_ocr": args.skip_ocr,
        "skip_convert": args.skip_convert,
        "ocr_langs": args.ocr_langs,
        "ocr_threshold": args.ocr_threshold,
        "ocr_shave": args.ocr_crop,
        "ocr_char_blacklist": args.ocr_blacklist,
        "use_existing_ocr": not args.ignore_original_ocr,
        "excl_patterns": excl_patterns,
        "keep_temp": args.keep_temp
    }

    page_data = convert_pages(files, tempdir, params)

    if page_data is None:
        logging.error("Page conversion failed")
        return 1

    djvu_files = [x['djvu'] for x in page_data]
    djvu_files.sort()
    DJVU.create_djvu_from_pages(djvu_files, args.out_djvu)

    if not args.keep_temp:
        logging.debug("Deleting temp dir: {}".format(tempdir))
        shutil.rmtree(tempdir)

    return 0


if __name__ == "__main__":
    main()
