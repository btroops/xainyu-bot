import asyncio, json, time, base64
from loguru import logger
from websockets.asyncio.client import connect
from src.utils.xianyu_utils import (
    trans_cookies, generate_mid, generate_uuid, generate_device_id, decrypt
)

class XianyuLiveClient:
    def __init__(self, settings, handler, api):
        self.settings = settings
        self.handler = handler
        self.api = api
        self.cookies = trans_cookies(settings.cookies_str)
        self.myid = self.cookies['unb']
        self.device_id = generate_device_id(self.myid)
        self.api.session.cookies.update(self.cookies)

        self.ws = None
        self.current_token = None
        self.last_token_refresh_time = 0
        self.connection_restart_flag = False
        self.base_url = 'wss://wss-goofish.dingtalk.com/'
        self.heartbeat_interval = settings.heartbeat_interval
        self.heartbeat_timeout = settings.heartbeat_timeout
        self.last_heartbeat_time = 0
        self.last_heartbeat_response = 0

    async def refresh_token(self):
        logger.info("刷新 token ...")
        res = self.api.get_token(self.device_id)
        if 'data' in res and 'accessToken' in res['data']:
            self.current_token = res['data']['accessToken']
            self.last_token_refresh_time = time.time()
            logger.info("token 刷新成功")
            return True
        logger.error("token 刷新失败")
        return False

    async def token_refresh_loop(self):
        while True:
            try:
                now = time.time()
                if now - self.last_token_refresh_time >= self.settings.token_refresh_interval:
                    if await self.refresh_token():
                        self.connection_restart_flag = True
                        if self.ws:
                            await self.ws.close()
                        break
                    else:
                        logger.error(f"刷新失败，{self.settings.token_retry_interval//60}分钟后重试")
                        await asyncio.sleep(self.settings.token_retry_interval)
                        continue
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"token 循环异常: {e}")
                await asyncio.sleep(60)

    async def send_msg(self, ws, cid, toid, text):
        text_obj = {"contentType": 1, "text": {"text": text}}
        text_b64 = base64.b64encode(json.dumps(text_obj).encode()).decode()
        msg = {
            "lwp": "/r/MessageSend/sendByReceiverScope",
            "headers": {"mid": generate_mid()},
            "body": [
                {
                    "uuid": generate_uuid(),
                    "cid": f"{cid}@goofish",
                    "conversationType": 1,
                    "content": {"contentType": 101, "custom": {"type": 1, "data": text_b64}},
                    "redPointPolicy": 0,
                    "extension": {"extJson": "{}"},
                    "ctx": {"appVersion": "1.0", "platform": "web"},
                    "mtags": {},
                    "msgReadStatusSetting": 1
                },
                {"actualReceivers": [f"{toid}@goofish", f"{self.myid}@goofish"]}
            ]
        }
        await ws.send(json.dumps(msg))

    async def init_connection(self, ws):
        if not self.current_token or (time.time() - self.last_token_refresh_time) >= self.settings.token_refresh_interval:
            await self.refresh_token()
        if not self.current_token:
            raise Exception("无法获取 token")
        init_msg = {
            "lwp": "/reg",
            "headers": {
                "cache-header": "app-key token ua wv",
                "app-key": "444e9908a51d1cb236a27862abc769c9",
                "token": self.current_token,
                "ua": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 DingTalk(2.1.5) OS(Windows/10) Browser(Chrome/133.0.0.0) DingWeb/2.1.5 IMPaaS DingWeb/2.1.5",
                "dt": "j",
                "wv": "im:3,au:3,sy:6",
                "sync": "0,0;0;0;",
                "did": self.device_id,
                "mid": generate_mid()
            }
        }
        await ws.send(json.dumps(init_msg))
        await asyncio.sleep(1)
        ack_msg = {
            "lwp": "/r/SyncStatus/ackDiff",
            "headers": {"mid": generate_mid()},
            "body": [{
                "pipeline": "sync", "tooLong2Tag": "PNM,1",
                "channel": "sync", "topic": "sync", "highPts": 0,
                "pts": int(time.time() * 1000) * 1000, "seq": 0,
                "timestamp": int(time.time() * 1000)
            }]
        }
        await ws.send(json.dumps(ack_msg))
        logger.info("连接注册完成")

    async def handle_ws_message(self, raw_msg, ws):
        try:
            data = json.loads(raw_msg)
        except:
            return
        if data.get("code") == 200 and "headers" in data and "mid" in data["headers"]:
            self.last_heartbeat_response = time.time()
            return
        if not isinstance(data, dict) or "body" not in data or "syncPushPackage" not in data["body"]:
            return
        data_list = data["body"]["syncPushPackage"]["data"]
        if not data_list:
            return  # 空数据直接返回，不处理
        sync_data = data_list[0]
        # sync_data = data["body"]["syncPushPackage"]["data"][0]
        if "data" not in sync_data:
            return
        try:
            decrypted = decrypt(sync_data["data"])
            msg = json.loads(decrypted)
        except Exception as e:
            logger.error(f"解密失败: {e}")
            return
        await self.handler.handle(msg, ws, self.myid)

    async def send_heartbeat(self, ws):
        hb = {"lwp": "/!", "headers": {"mid": generate_mid()}}
        await ws.send(json.dumps(hb))
        self.last_heartbeat_time = time.time()

    async def heartbeat_loop(self, ws):
        while True:
            try:
                now = time.time()
                if now - self.last_heartbeat_time >= self.heartbeat_interval:
                    await self.send_heartbeat(ws)
                if (now - self.last_heartbeat_response) > (self.heartbeat_interval + self.heartbeat_timeout):
                    logger.warning("心跳超时，连接可能已断开")
                    break
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"心跳循环错误: {e}")
                break

    async def run(self):
        while True:
            try:
                self.connection_restart_flag = False
                headers = {
                    "Cookie": self.settings.cookies_str,
                    "Origin": "https://www.goofish.com",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ..."
                }
                async with connect(self.base_url, additional_headers=headers) as ws:
                    self.ws = ws
                    await self.init_connection(ws)
                    self.last_heartbeat_time = time.time()
                    self.last_heartbeat_response = time.time()
                    heartbeat_task = asyncio.create_task(self.heartbeat_loop(ws))
                    token_task = asyncio.create_task(self.token_refresh_loop())
                    async for raw in ws:
                        if self.connection_restart_flag:
                            break
                        try:
                            msg_data = json.loads(raw)
                            if "headers" in msg_data and "mid" in msg_data["headers"]:
                                ack = {"code": 200, "headers": {"mid": msg_data["headers"]["mid"], "sid": msg_data["headers"].get("sid", "")}}
                                for key in ["app-key", "ua", "dt"]:
                                    if key in msg_data["headers"]:
                                        ack["headers"][key] = msg_data["headers"][key]
                                await ws.send(json.dumps(ack))
                        except:
                            pass
                        await self.handle_ws_message(raw, ws)
                    heartbeat_task.cancel()
                    token_task.cancel()
            except Exception as e:
                logger.error(f"连接异常: {e}")
                await asyncio.sleep(5)