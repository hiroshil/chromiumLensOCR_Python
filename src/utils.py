import time

def parse_cookies(cookies):
    return {
        name: '='.join(value)
        for cookie in cookies.split('; ')
        for name, *value in [cookie.split('=')]
    }
    
def replace_keys(text):
    pattern = r"(\w+):\s*(?:'[^']*'|\{[^}]*\}|\[[^\]]*\])"
    matches = re.findall(pattern, text)
    for m in matches:
        text = text.replace(m, f"'{m}'")
    return text

async def sleep(ms):
    await asyncio.sleep(ms / 1000)

