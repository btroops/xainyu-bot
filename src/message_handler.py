import time, asyncio, random
from loguru import logger
from langchain_openai import ChatOpenAI
from src.config import Settings
from src.conversation.memory import (
    get_memory, save_context, increment_bargain_count_db, get_bargain_count_db
)
from src.conversation.manual_control import ManualControl
from src.chain_factory import build_reply_chain
from src.utils.item_utils import get_item_desc
from src.utils.xianyu_apis import XianyuApis

class MessageHandler:
    def __init__(self, settings: Settings, llm: ChatOpenAI, api: XianyuApis):
        self.settings = settings
        self.llm = llm
        self.api = api
        self.manual_control = ManualControl(settings.manual_mode_timeout)
        self.toggle_keywords = settings.toggle_keywords
        self.message_expire_time = settings.message_expire_time
        self.pending_replies = {}   # key: chat_id, value: (to_id, reply_text)

    async def handle(self, msg: dict, ws, myid: str):
        if not self._is_chat_message(msg):
            return
        create_time = int(msg["1"]["5"])
        if (time.time() * 1000 - create_time) > self.message_expire_time:
            logger.debug("过期消息丢弃")
            return

        send_user_id = msg["1"]["10"]["senderUserId"]
        send_message = msg["1"]["10"]["reminderContent"]
        url_info = msg["1"]["10"]["reminderUrl"]
        item_id = url_info.split("itemId=")[1].split("&")[0] if "itemId=" in url_info else None
        chat_id = msg["1"]["2"].split('@')[0]
        if not item_id:
            return
        # ---- 在正常回复前，先尝试发送该会话之前未发出去的消息 ----
        if chat_id in self.pending_replies:
            to_id, old_reply = self.pending_replies.pop(chat_id)
            logger.info(f"补发会话 {chat_id} 的未发送回复: {old_reply}")
            try:
                await self._send_message(ws, chat_id, to_id, myid, old_reply)
            except Exception:
                # 如果仍然发送失败，重新放回队列
                self.pending_replies[chat_id] = (to_id, old_reply)
        # 卖家自己的消息
        if send_user_id == myid:
            if send_message.strip() in self.toggle_keywords:
                mode = self.manual_control.toggle(chat_id)
                logger.info(f"{'🔴 接管' if mode == 'manual' else '🟢 恢复自动'} 会话 {chat_id}")
                return
            mem = get_memory(chat_id, self.settings.db_path)
            save_context(mem, "", send_message)  # 记录助手消息
            return

        logger.info(f"用户 {send_user_id} 商品 {item_id}: {send_message}")

        # 人工接管模式
        if self.manual_control.is_manual(chat_id):
            mem = get_memory(chat_id, self.settings.db_path)
            save_context(mem, send_message, "")  # 只记录用户消息
            return

        # 获取商品描述
        # item_desc = get_item_desc(item_id, self.api, self.settings.db_path)
        item_desc = await asyncio.to_thread(get_item_desc, item_id, self.api, self.settings.db_path)
        # 获取记忆和议价次数
        mem = get_memory(chat_id, self.settings.db_path)
        bargain_count = get_bargain_count_db(chat_id, self.settings.db_path)
        mem.bargain_count = bargain_count

        # 构建链
        chain = build_reply_chain(mem, item_desc, self.llm)
        # 在 handle 中构建 inputs
        inputs = {
            "input": send_message,
            "bargain_count": bargain_count,
        }
        memory_vars = mem.load_memory_variables(inputs)
        inputs.update(memory_vars)          # inputs 现在包含 "history" (字符串) 和 "bargain_count"

        result = await chain.ainvoke(inputs)

        intent = result.get("intent", "default")
        reply = result.get("reply", "").strip()

        if reply == "-":
            return

        # 保存对话
        save_context(mem, send_message, reply)
        if intent == "price":
            increment_bargain_count_db(chat_id, self.settings.db_path)
            logger.info("议价轮次+1")

        # 模拟人工延迟
        if self.settings.simulate_human_typing:
            delay = min(len(reply) * random.uniform(0.1, 0.3), 10.0)
            await asyncio.sleep(delay)

        # await self._send_message(ws, chat_id, send_user_id, myid, reply)
        # 在发送回复时，如果失败则存入队列
        try:
            await self._send_message(ws, chat_id, send_user_id, myid, reply)
        except Exception as e:
            logger.error(f"发送消息失败，存入待发送队列: {e}")
            self.pending_replies[chat_id] = (send_user_id, reply)

    async def _send_message(self, ws, chat_id, to_id, myid, text):
        import json, base64
        from src.utils.xianyu_utils import generate_mid, generate_uuid
        text_obj = {"contentType": 1, "text": {"text": text}}
        text_b64 = base64.b64encode(json.dumps(text_obj).encode()).decode()
        msg = {
            "lwp": "/r/MessageSend/sendByReceiverScope",
            "headers": {"mid": generate_mid()},
            "body": [
                {
                    "uuid": generate_uuid(),
                    "cid": f"{chat_id}@goofish",
                    "conversationType": 1,
                    "content": {"contentType": 101, "custom": {"type": 1, "data": text_b64}},
                    "redPointPolicy": 0,
                    "extension": {"extJson": "{}"},
                    "ctx": {"appVersion": "1.0", "platform": "web"},
                    "mtags": {},
                    "msgReadStatusSetting": 1
                },
                {"actualReceivers": [f"{to_id}@goofish", f"{myid}@goofish"]}
            ]
        }
        await ws.send(json.dumps(msg))

    def _is_chat_message(self, msg: dict) -> bool:
        try:
            return (isinstance(msg, dict) and "1" in msg
                    and isinstance(msg["1"], dict) and "10" in msg["1"]
                    and "reminderContent" in msg["1"]["10"])
        except:
            return False