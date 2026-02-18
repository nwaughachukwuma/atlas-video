import mimetypes

# Custom MIME type to extension mappings
CUSTOM_MIME_MAPPINGS = {
    "audio/x-m4a": ".m4a",
}


def get_file_extension(file_path: str):
    """
    Get the file extension from the file content-type.

    It's risky to consider the following fallback -> Path(file_path).suffix
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        raise ValueError(f"Unsupported MIME type: {mime_type}")

    return get_ext_from_mimetype(mime_type)


def get_ext_from_mimetype(mime_type: str):
    """
    Get the file extension from the mime/content type.
    """
    if mime_type in CUSTOM_MIME_MAPPINGS:
        return CUSTOM_MIME_MAPPINGS[mime_type]

    # Add support for audio/m4a mime type
    mimetypes.add_type("audio/m4a", ".m4a")
    extension = mimetypes.guess_extension(mime_type)
    if not extension:
        raise ValueError(f"Unsupported MIME type: {mime_type}")
    return extension


def get_content_type(file_path: str) -> str:
    return mimetypes.guess_type(file_path)[0] or ""
