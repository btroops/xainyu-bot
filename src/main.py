import asyncio, sys, os
from loguru import logger
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from src.config import Settings
from src.live_client import XianyuLiveClient
from src.message_handler import MessageHandler
from src.utils.xianyu_apis import XianyuApis
from src.utils.item_utils import init_db
from requests.utils import dict_from_cookiejar, cookiejar_from_dict
def setup_logging(level: str):
    logger.remove()
    logger.add(sys.stderr, level=level,
               format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>")

async def main():
    load_dotenv()
    settings = Settings()
    setup_logging(settings.log_level)

    # 初始化数据库目录和表
    init_db(settings.db_path)

    llm = ChatOpenAI(
        model=settings.model_name,
        api_key=settings.api_key,
        base_url=settings.model_base_url,
        temperature=0.4,
        # proxies=None,
    )
    xianyu_api = XianyuApis()
    # xianyu_api.session.cookies = cookiejar_from_dict({k: v for k, v in [c.split('=', 1) for c in settings.cookies_str.split('; ')]})
    cookie_dict = {}
    for item in settings.cookies_str.split("; "):
        if "=" in item:
            k, v = item.split("=", 1)
            cookie_dict[k] = v
    # settings.cookies_str = cookie_dict
    print(xianyu_api.session.cookies)
    xianyu_api.session.cookies.update(cookie_dict)

    handler = MessageHandler(settings, llm, xianyu_api)
    client = XianyuLiveClient(settings, handler, xianyu_api)
    await client.run()

if __name__ == "__main__":
    asyncio.run(main())