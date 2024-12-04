import os
import aiofiles
from filetype import guess_mime
from PIL import Image
from .consts import global_fetch
import io

from src.core import LensCore, LensResult, LensError, Segment, BoundingBox

class Lens(LensCore):
    def __init__(self, config=None, _fetch=None):
        if not isinstance(config, dict):
            print(f"Lens constructor expects a dictionary, got {type(config)}")
            config = {}

        fetch_fn = _fetch or global_fetch

        super().__init__(config, fetch_fn)

    async def scan_by_file(self, path):
        if not isinstance(path, str):
            raise TypeError(f"scan_by_file expects a string, got {type(path)}")

        try:
            os.access(path, os.R_OK)
        except OSError as error:
            if error.errno == errno.EACCES:
                raise PermissionError(f"Read permission denied: {path}")
            elif error.errno == errno.ENOENT:
                raise FileNotFoundError(f"File not found: {path}")
            elif error.errno == errno.EISDIR:
                raise IsADirectoryError(f"Expected file, Found directory: {path}")

        async with aiofiles.open(path, mode='rb') as file:
            buffer = await file.read()

        return await self.scan_by_buffer(buffer)

    async def scan_by_buffer(self, buffer):
        mime_type = guess_mime(buffer)

        if not mime_type:
            raise ValueError('File type not supported')

        image = Image.open(io.BytesIO(buffer))
        width, height = image.size

        # Google Lens does not accept images larger than 1000x1000
        if width > 1000 or height > 1000:
            image.thumbnail((1000, 1000))
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=90, progressive=True)
            width, height = image.size
            buffer = output.getvalue()
            mime_type = 'image/jpeg'

        return await self.scan_by_data(buffer, mime_type, [width, height])

