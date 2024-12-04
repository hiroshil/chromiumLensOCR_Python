import io
import re
import time
from datetime import datetime
from aiohttp import FormData
from PIL import Image
from .set_cookie_parser import split_cookies_string, parse as cookie_parse
from .consts import LENS_API_ENDPOINT, LENS_ENDPOINT, MIME_TO_EXT, SUPPORTED_MIMES
from .utils import parse_cookies, replace_keys, sleep
from urllib.parse import urlparse, urlencode

class BoundingBox:
    def __init__(self, box, image_dimensions):
        if not box:
            raise ValueError('Bounding box not set')
        if not image_dimensions or len(image_dimensions) != 2:
            raise ValueError('Image dimensions not set')

        self._image_dimensions = image_dimensions

        self.center_per_x = box[0]
        self.center_per_y = box[1]
        self.per_width = box[2]
        self.per_height = box[3]
        self.pixel_coords = self._to_pixel_coords()

    def _to_pixel_coords(self):
        img_width, img_height = self._image_dimensions

        width = self.per_width * img_width
        height = self.per_height * img_height

        x = (self.center_per_x * img_width) - (width / 2)
        y = (self.center_per_y * img_height) - (height / 2)

        return {
            'x': round(x),
            'y': round(y),
            'width': round(width),
            'height': round(height)
        }

class LensError(Exception):
    def __init__(self, message, code, headers, body):
        super().__init__(message)
        self.name = 'LensError'
        self.code = code
        self.headers = headers
        self.body = body

class Segment:
    def __init__(self, text, bounding_box, image_dimensions):
        self.text = text
        self.bounding_box = BoundingBox(bounding_box, image_dimensions)

class LensResult:
    def __init__(self, language, segments):
        self.language = language
        self.segments = segments

class LensCore:
    def __init__(self, config=None, fetch=None):
        self._config = {}
        self.cookies = {}
        self._fetch = fetch or global_fetch

        if config is None:
            config = {}
        if not isinstance(config, dict):
            raise TypeError('Lens constructor expects an object')

        chrome_version = config.get('chromeVersion', '124.0.6367.60')
        major_chrome_version = chrome_version.split('.')[0]

        self._config = {
            'chromeVersion': chrome_version,
            'majorChromeVersion': major_chrome_version,
            'sbisrc': f'Google Chrome {chrome_version} (Official) Windows',
            'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'endpoint': LENS_ENDPOINT,
            'viewport': [1920, 1080],
            'headers': {},
            #'fetchOptions': {},
            **config
        }

        # lowercase all headers
        for key in list(self._config['headers'].keys()):
            value = self._config['headers'][key]
            if not value:
                del self._config['headers'][key]
                continue
            if key.lower() != key:
                del self._config['headers'][key]
                self._config['headers'][key.lower()] = value

        self._parse_cookies()

    def update_options(self, options):
        for key, value in options.items():
            self._config[key] = value

        self._parse_cookies()

    async def fetch(self, options=None, original_dimensions=None, second_try=False):
        if options is None:
            options = {}
        if original_dimensions is None:
            original_dimensions = [0, 0]

        url = urlparse(options.get('endpoint', self._config['endpoint']))
        params = url.query

        params += f'&s=4&re=df&stcs={int(time.time())}&vpw={self._config["viewport"][0]}&vph={self._config["viewport"][1]}&ep=subb'

        headers = self._generate_headers()

        for key, value in self._config['headers'].items():
            headers[key] = value

        headers['cookie'] = self._generate_cookie_header(headers)

        url_query = f"{url.scheme}://{url.netloc}{url.path}?{params}"
        response = await self._fetch(url_query, {
            'headers': headers,
            'redirect': 'manual',
            **options,
            #**self._config['fetchOptions']
        })

        text = response.get("text")

        cookie_string = "; ".join([str(value) for _, value in response.get("cookies").items()]).replace('Set-Cookie: ', '')
        self._set_cookies(cookie_string) #response.headers.get('set-cookie'))

        # in some of the EU countries, Google requires cookie consent
        if response.get("status") == 302:
            if second_try:
                raise LensError('Lens returned a 302 status code twice', response.get("status"), response.get("headers"), text)

            consent_headers = self._generate_headers()
            consent_headers['Content-Type'] = 'application/x-www-form-urlencoded'
            consent_headers['Referer'] = 'https://consent.google.com/'
            consent_headers['Origin'] = 'https://consent.google.com'

            consent_headers['cookie'] = self._generate_cookie_header(consent_headers)

            location = response.get("headers").get('Location')

            if not location:
                raise ValueError('Location header not found')

            redirect_link = urlparse(location)
            params = redirect_link.query
            params += '&x=6&set_eom=true&bl=boq_identityfrontenduiserver_20240129.02_p0&app=0'

            await sleep(500)  # to not be suspicious
            save_consent_request = await fetch('https://consent.google.com/save', {
                'method': 'POST',
                'headers': consent_headers,
                'body': params,
                'redirect': 'manual'
            })

            if save_consent_request.status == 303:
                # consent was saved, save new cookies and retry the request
                cookie_string = "; ".join([str(value) for _, value in save_consent_request.cookies.items()]).replace('Set-Cookie: ', '')
                self._set_cookies(cookie_string)
                await sleep(500)
                return await self.fetch({}, original_dimensions, True)

        if response.get("status") != 200:
            raise LensError('Lens returned a non-200 status code', response.get("status"), response.get("headers"), text)

        try:
            af_data = LensCore.get_af_data(text)
            return LensCore.parse_result(af_data, original_dimensions)
        except Exception as e:
            raise LensError(f'Could not parse response: {str(e)}', response.get("status"), response.get("headers"), text)

    async def scan_by_url(self, url, dimensions=None):
        if dimensions is None:
            dimensions = [0, 0]

        endpoint = urlparse(LENS_API_ENDPOINT)
        endpoint_query = f"{endpoint.scheme}://{endpoint.netloc}{endpoint.path}?{urlencode({'url': str(url)})}"

        options = {
            'endpoint': endpoint_query,
            'method': 'GET',
        }

        return await self.fetch(options, dimensions)

    async def scan_by_data(self, uint8, mime, original_dimensions):
        if mime not in SUPPORTED_MIMES:
            raise ValueError('File type not supported')
        if not original_dimensions:
            raise ValueError('Original dimensions not set')

        file_name = f'image.{MIME_TO_EXT[mime]}'

        image = Image.open(io.BytesIO(uint8))
        dimensions = image.size
        if not dimensions:
            raise ValueError('Could not determine image dimensions')

        width, height = dimensions
        # Google Lens does not accept images larger than 1000x1000
        if width > 1000 or height > 1000:
            raise ValueError('Image dimensions are larger than 1000x1000')

        formdata = FormData()

        formdata.add_field('encoded_image', uint8, filename=file_name, content_type=mime)
        formdata.add_field('original_width', str(width))
        formdata.add_field('original_height', str(height))
        formdata.add_field('processed_image_dimensions', f'{width},{height}')

        options = {
            'endpoint': LENS_ENDPOINT,
            'method': 'POST',
            'body': formdata,
        }

        return await self.fetch(options, original_dimensions)

    def _generate_headers(self):
        return {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'max-age=0',
            'Origin': 'https://lens.google.com',
            'Referer': 'https://lens.google.com/',
            'Sec-Ch-Ua': f'"Not A(Brand";v="99", "Google Chrome";v="{self._config["majorChromeVersion"]}", "Chromium";v="{self._config["majorChromeVersion"]}"',
            'Sec-Ch-Ua-Arch': '"x86"',
            'Sec-Ch-Ua-Bitness': '"64"',
            'Sec-Ch-Ua-Full-Version': f'"{self._config["chromeVersion"]}"',
            'Sec-Ch-Ua-Full-Version-List': f'"Not A(Brand";v="99.0.0.0", "Google Chrome";v="{self._config["majorChromeVersion"]}", "Chromium";v="{self._config["majorChromeVersion"]}"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Model': '""',
            'Sec-Ch-Ua-Platform': '"Windows"',
            'Sec-Ch-Ua-Platform-Version': '"15.0.0"',
            'Sec-Ch-Ua-Wow64': '?0',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
            'Sec-Fetch-User': '?1',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': self._config['userAgent'],
            'X-Client-Data': 'CIW2yQEIorbJAQipncoBCIH+ygEIlaHLAQj1mM0BCIWgzQEI3ezNAQji+s0BCOmFzgEIponOAQj1ic4BCIeLzgEY1d3NARjS/s0BGNiGzgE='
        }

    def _generate_cookie_header(self, header):
        if self.cookies:
            self.cookies = {name: cookie for name, cookie in self.cookies.items() if datetime.strptime(cookie['expires'].strip(), '%a, %d-%b-%Y %H:%M:%S GMT') > datetime.now()}#cookie['expires'] > time.time()}
            header['cookie'] = '; '.join([f'{name}={cookie["value"]}' for name, cookie in self.cookies.items()])
            return header['cookie']
        return str()

    def _set_cookies(self, combined_cookie_header):
        split_cookie_headers = split_cookies_string(combined_cookie_header)
        cookies = cookie_parse(split_cookie_headers)

        if cookies:
            for cookie in cookies:
                self.cookies[cookie['name']] = cookie

    def _parse_cookies(self):
        if 'cookie' in self._config.get('headers', {}):
            if isinstance(self._config['headers']['cookie'], str):
                # parse cookies from string
                cookies = parse_cookies(self._config['headers']['cookie'])
                for cookie in cookies:
                    self.cookies[cookie] = {
                        'name': cookie,
                        'value': cookies[cookie],
                        'expires': float('inf')
                    }
            else:
                self.cookies = self._config['headers']['cookie']

    @staticmethod
    def get_af_data(text):
        callbacks = re.findall(r'AF_initDataCallback\((\{.*?\})\)', text, re.DOTALL)
        lens_callback = next((c for c in callbacks if 'DetectedObject' in c), None)

        if not lens_callback:
            print(callbacks)
            raise ValueError('Could not find matching AF_initDataCallback')

        capitalize_string = re.sub(r"(false|true)", lambda m: m.group(1).capitalize(), lens_callback)
        matched = replace_keys(capitalize_string.replace("null", "None"))
        return eval(matched)

    @staticmethod
    def parse_result(af_data, image_dimensions):
        data = af_data['data']
        full_text_part = data[3]
        text_segments = []
        text_regions = []

        try:
            # method 1, get text segments and regions directly
            text_segments = full_text_part[4][0][0]
            text_regions = [x[1] for x in data[2][3][0] if x[11].startswith("text:")]
        except Exception:
            # method 2
            # sometimes the text segments are not directly available
            # try to get them from text parts
            big_parts = full_text_part[2][0]
            for big_part in big_parts:
                parts = big_part[0]
                for part in parts:
                    text = ''.join(b[0] + (b[3] if b[3] else '') for b in part[0])

                    # region data is different format from method 1
                    # instead of [centerX, centerY, width, height] it's [topLeftY, topLeftX, width, height]
                    # so we need to convert it
                    region = part[1]
                    y, x, width, height = region
                    center_x = x + (width / 2)
                    center_y = y + (height / 2)
                    region = [center_x, center_y, width, height]

                    text_segments.append(text)
                    text_regions.append(region)

        segments = [Segment(text_segments[i], text_regions[i], image_dimensions) for i in range(len(text_segments))]

        return LensResult(full_text_part[3], segments)

