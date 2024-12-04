import urllib.parse
from typing import Dict, List, Union

default_parse_options = {
    "decodeValues": True,
    "map": False,
    "silent": False,
}

def is_non_empty_string(s: str) -> bool:
    return isinstance(s, str) and bool(s.strip())

def parse_string(set_cookie_value: str, options: Dict = None) -> Dict:
    parts = [part for part in set_cookie_value.split(";") if is_non_empty_string(part)]

    name_value_pair_str = parts.pop(0)
    parsed = parse_name_value_pair(name_value_pair_str)
    name, value = parsed["name"], parsed["value"]

    options = {**default_parse_options, **(options or {})}

    try:
        value = urllib.parse.unquote(value) if options["decodeValues"] else value
    except Exception as e:
        print(f"set-cookie-parser encountered an error while decoding a cookie with value '{value}'. Set options.decodeValues to False to disable this feature.", e)

    cookie = {
        "name": name,
        "value": value,
    }

    for part in parts:
        sides = part.split("=")
        key = sides.pop(0).lstrip().lower()
        value = "=".join(sides)
        if key == "expires":
            cookie["expires"] = value  # You might want to parse this into a datetime object
        elif key == "max-age":
            cookie["maxAge"] = int(value)
        elif key == "secure":
            cookie["secure"] = True
        elif key == "httponly":
            cookie["httpOnly"] = True
        elif key == "samesite":
            cookie["sameSite"] = value
        elif key == "partitioned":
            cookie["partitioned"] = True
        else:
            cookie[key] = value

    return cookie

def parse_name_value_pair(name_value_pair_str: str) -> Dict[str, str]:
    name = ""
    value = ""
    name_value_arr = name_value_pair_str.split("=")
    if len(name_value_arr) > 1:
        name = name_value_arr.pop(0)
        value = "=".join(name_value_arr)
    else:
        value = name_value_pair_str

    return {"name": name, "value": value}

def parse(input_data: Union[str, List[str], Dict], options: Dict = None) -> Union[List[Dict], Dict]:
    options = {**default_parse_options, **(options or {})}

    if not input_data:
        return {} if options["map"] else []

    if isinstance(input_data, dict) and "headers" in input_data:
        headers = input_data["headers"]
        if callable(getattr(headers, "getSetCookie", None)):
            input_data = headers.getSetCookie()
        elif "set-cookie" in headers:
            input_data = headers["set-cookie"]
        else:
            sch = next((headers[key] for key in headers if key.lower() == "set-cookie"), None)
            if not sch and "cookie" in headers and not options["silent"]:
                print("Warning: set-cookie-parser appears to have been called on a request object. It is designed to parse Set-Cookie headers from responses, not Cookie headers from requests. Set the option {silent: True} to suppress this warning.")
            input_data = sch

    if not isinstance(input_data, list):
        input_data = [input_data]

    if not options["map"]:
        return [parse_string(s, options) for s in input_data if is_non_empty_string(s)]
    else:
        return {parse_string(s, options)["name"]: parse_string(s, options) for s in input_data if is_non_empty_string(s)}

def split_cookies_string(cookies_string: Union[str, List[str]]) -> List[str]:
    if isinstance(cookies_string, list):
        return cookies_string
    if not isinstance(cookies_string, str):
        return []

    cookies_strings = []
    pos = 0
    start = 0
    last_comma = 0

    def skip_whitespace():
        nonlocal pos
        while pos < len(cookies_string) and cookies_string[pos].isspace():
            pos += 1
        return pos < len(cookies_string)

    def not_special_char():
        return cookies_string[pos] not in "=;,"

    while pos < len(cookies_string):
        start = pos
        cookie_separator_found = False

        while skip_whitespace():
            if cookies_string[pos] == ",":
                last_comma = pos
                pos += 1
                skip_whitespace()
                next_start = pos

                while pos < len(cookies_string) and not_special_char():
                    pos += 1

                if pos < len(cookies_string) and cookies_string[pos] == "=":
                    cookie_separator_found = True
                    pos = next_start
                    cookies_strings.append(cookies_string[start:last_comma])
                    start = pos
                else:
                    pos = last_comma + 1
            else:
                pos += 1

        if not cookie_separator_found or pos >= len(cookies_string):
            cookies_strings.append(cookies_string[start:])

    return cookies_strings


