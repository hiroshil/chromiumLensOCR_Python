import pyperclip
import asyncio
from src.utils import sleep
from cli import cli

async def main():
    try:
        args = sys.argv[1:]
        result = await cli(args)

        pyperclip.copy(result)
    except Exception as e:
        print('Error occurred:')
        print(e)
        await sleep(30)

if __name__ == "__main__":
    asyncio.run(main())

