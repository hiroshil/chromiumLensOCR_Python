import os
import json
import sys
import asyncio
import pyperclip
from pathlib import Path
from urllib.parse import urlparse
from src.index import Lens

image = None
should_copy = True

def asyncio_run(func):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(func)
async def cli(args):
    global should_copy, image

    if '-d' in args:
        args.remove('-d')
        should_copy = False

    # check empty arguments at last
    if not args or '-h' in args or '--help' in args:
        print('Scan text from image using Google Lens and copy to clipboard.')
        print('')
        print('USAGE:')
        print('    chrome-lens-ocr [-d] ./path/to/image.png')
        print('    chrome-lens-ocr [-d] https://domain.tld/image.png')
        print('    chrome-lens-ocr --help')
        print('ARGS:')
        print('    -d         Do not copy text to clipboard')
        print('    -h, --help Show this message')
        return

    # hope the last argument is the image
    image = args[0]

    # get path to cookies file (should be in the same directory as this script)
    module_url = Path(__file__).resolve()
    path_to_cookies = module_url.parent / 'cookies.json'

    # check file access
    # if not os.access(path_to_cookies, os.R_OK | os.W_OK):
        # print(f'Cannot write cookie, read/write permission denied in {path_to_cookies}')
        # return

    # read cookies from file
    cookie = None
    if path_to_cookies.exists():
        with open(path_to_cookies, 'r', encoding='utf8') as f:
            cookie = json.load(f)

    # create lens instance, with cookie if exists
    lens_options = {'headers': {'cookie': cookie}} if cookie else {}
    lens = Lens(lens_options)
    text = None

    # remove Windows drive prefix because false positive
    if urlparse(image).scheme in ['http', 'https']:
        text = await lens.scan_by_url(image)
    else:
        text = await lens.scan_by_file(image)

    result = '\n'.join(segment.text for segment in text.segments)

    # write cookies to file
    with open(path_to_cookies, 'w', encoding='utf8') as f:
        json.dump(lens.cookies, f, indent=4)

    # write text to clipboard
    if should_copy:
        pyperclip.copy(result)

    print(result)
    return result

# only run if directly executed
if __name__ == '__main__':
    try:
        args = sys.argv[1:]
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(cli(args))
    except Exception as e:
        print('Error occurred:')
        print(e)

