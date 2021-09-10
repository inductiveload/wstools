

def mime_to_ext(mime):

    if mime == "image/png":
        ext = ".png"
    elif mime in ["image/jpeg", "image/jpg"]:
        ext = ".jpg"
    else:
        raise ValueError("Unknown mimetype: {}".format(mime))

    return ext


def image_exts():
    """
    Exts that might be returned by this module
    """
    return [".jpg", ".png", ".tiff", ".pbm", ".pnm", ".jp2"]
