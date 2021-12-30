
import os
import zipfile


def get_image_exts():
    return [".jpg", ".jpeg", ".jp2", ".png", ".pnm", ".pbm", ".tif", ".tiff"]


def dir_has_any_images(d):

    exts = get_image_exts()
    for name in os.listdir(d):

        if os.path.isfile(os.path.join(d, name)):
            _, ext = os.path.splitext(name)

            if ext.lower() in exts:
                return True

    return False


def skip_interposed_directory(d):

    have_img_files = dir_has_any_images(d)

    subdirs = [name for name in os.listdir(d) if
               os.path.isdir(os.path.join(d, name))]

    if len(subdirs) != 1 or have_img_files:
        return d

    return os.path.join(d, subdirs[0])


def get_dir_list_with_exts(d, want_exts):

    def want(f):
        _, ext = os.path.splitext(f)
        return os.path.isfile(f) and ext.lower() in want_exts

    files = [os.path.join(d, f) for f in os.listdir(d) if want(os.path.join(d, f))]

    files.sort()

    return files


def extract_zip_to(zip_fo, dir_name, excluder=None):

    with zipfile.ZipFile(zip_fo) as zip_ref:
        if not excluder:
            zip_ref.extractall(dir_name)
        else:
            for member in zip_ref.infolist():

                if not excluder(member):
                    zip_ref.extract(member, dir_name)