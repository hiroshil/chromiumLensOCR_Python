from typing import List, Dict, Tuple, Union
from dataclasses import dataclass
import aiohttp

LENS_ENDPOINT = 'https://lens.google.com/v3/upload'
LENS_API_ENDPOINT = 'https://lens.google.com/uploadbyurl'
SUPPORTED_MIMES = [
    'image/x-icon',
    'image/bmp',
    'image/jpeg',
    'image/png',
    'image/tiff',
    'image/webp',
    'image/heic',
]

MIME_TO_EXT = {
    'image/x-icon': 'ico',
    'image/bmp': 'bmp',
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/tiff': 'tiff',
    'image/webp': 'webp',
    'image/heic': 'heic'
}

async def global_fetch(url, request_init):
    allowed_properties = ["endpoint", "method", "headers", "body", "redirect"]
    for key in request_init:
        if key not in allowed_properties:
            print(f"Error: Unsupported property '{key}' found in request_init.")
            raise SystemExit(1)
    kwargs = {'headers': '', 'data': None, 'allow_redirects': True}
    method = request_init.get('method', 'GET').upper()  # Ensure uppercase for HTTP methods
    if 'headers' in request_init:
        kwargs['headers'] = request_init['headers']
    if 'body' in request_init:
        kwargs['data'] = request_init['body'] # Use 'data' for body in aiohttp
    if 'redirect' in request_init:
        if request_init['redirect'] != "follow"
            kwargs['allow_redirects'] = False
    async with aiohttp.ClientSession() as session:
        async with session.request(method, url, **kwargs) as response:
            response.raise_for_status()  # Raise an exception for error HTTP statuses
            return dict(status = response.status, headers = dict(response.headers), cookies = response.cookies, text = await response.text())

@dataclass
class LensOptions:
    chrome_version: str
    major_chrome_version: str
    user_agent: str
    endpoint: str
    viewport: Tuple[int, int]
    headers: Dict[str, str]
    fetch_options: Dict[str, Union[str, int, bool]]

@dataclass
class BoundingBox:
    center_per_x: float
    center_per_y: float
    per_width: float
    per_height: float
    pixel_coords: Dict[str, int]

@dataclass
class Segment:
    text: str
    bounding_box: BoundingBox

@dataclass
class LensResult:
    language: str
    segments: List[Segment]

class LensError(Exception):
    def __init__(self, message: str, code: str, headers: Dict[str, str], body: str):
        super().__init__(message)
        self.name = 'LensError'
        self.code = code
        self.headers = headers
        self.body = body

class LensCore:
    def __init__(self, options: Dict[str, Union[str, Tuple[int, int], Dict[str, str]]] = None, _fetch_function=None):
        self.cookies = None  # NavigatorCookies equivalent not available in Python
        self.options = options or {}
        self._fetch_function = _fetch_function or global_fetch

    def update_options(self, options: Dict[str, Union[str, Tuple[int, int], Dict[str, str]]]):
        self.options.update(options)

    def scan_by_url(self, url: str, dimensions: Tuple[int, int] = None) -> LensResult:
        # Implementation details would go here
        pass

    def scan_by_data(self, data: bytes, mime: str, original_dimensions: Tuple[int, int]) -> LensResult:
        # Implementation details would go here
        pass

    @staticmethod
    def get_af_data(text: str) -> dict:
        # Implementation details would go here
        pass

    @staticmethod
    def parse_result(af_data: dict, image_dimensions: Tuple[int, int]) -> LensResult:
        # Implementation details would go here
        pass

class Lens(LensCore):
    def __init__(self, options: Dict[str, Union[str, Tuple[int, int], Dict[str, str]]] = None, _fetch_function=None):
        super().__init__(options, _fetch_function)

    def scan_by_file(self, path: str) -> LensResult:
        # Implementation details would go here
        pass

    def scan_by_buffer(self, buffer: bytes) -> LensResult:
        # Implementation details would go here
        pass

