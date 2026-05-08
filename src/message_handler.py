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
        """快速解析消息，非耗时操作立即返回，耗时生成放入后台任务"""
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

        # ---- 补发该会话之前未发出去的消息 ----
        if chat_id in self.pending_replies:
            to_id, old_reply = self.pending_replies.pop(chat_id)
            logger.info(f"补发会话 {chat_id} 的未发送回复: {old_reply}")
            try:
                await self._send_message(ws, chat_id, to_id, myid, old_reply)
            except Exception:
                self.pending_replies[chat_id] = (to_id, old_reply)

        # 卖家自己的消息（控制命令或人工回复）
        if send_user_id == myid:
            if send_message.strip() in self.toggle_keywords:
                mode = self.manual_control.toggle(chat_id)
                logger.info(f"{'🔴 接管' if mode == 'manual' else '🟢 恢复自动'} 会话 {chat_id}")
                return
            # 记录助手消息（人工接管模式时的回复）
            mem = get_memory(chat_id, self.settings.db_path)
            save_context(mem, "", send_message)
            return

        logger.info(f"用户 {send_user_id} 商品 {item_id}: {send_message}")

        # 人工接管模式只记录用户消息，不回复
        if self.manual_control.is_manual(chat_id):
            mem = get_memory(chat_id, self.settings.db_path)
            save_context(mem, send_message, "")
            return

        # ---- 启动后台任务生成回复 ----
        asyncio.create_task(
            self._generate_and_reply(ws, myid, chat_id, send_user_id, send_message, item_id)
        )

    async def _generate_and_reply(self, ws, myid, chat_id, to_id, user_msg, item_id):
        """后台任务：获取商品信息、构建链、生成回复并发送"""
        try:
            # 1. 获取商品描述（可能涉及 API 调用，放到线程池）
            item_desc = await asyncio.to_thread(
                get_item_desc, item_id, self.api, self.settings.db_path
            )

            # 2. 获取记忆和议价次数
            mem = get_memory(chat_id, self.settings.db_path)
            bargain_count = get_bargain_count_db(chat_id, self.settings.db_path)
            mem.bargain_count = bargain_count

            # 3. 构建 LLM 链
            chain = build_reply_chain(mem, item_desc, self.llm)
            inputs = {
                "input": user_msg,
                "bargain_count": bargain_count,
            }
            memory_vars = mem.load_memory_variables(inputs)
            inputs.update(memory_vars)

            # 4. 调用 LLM 生成回复
            result = await chain.ainvoke(inputs)
            intent = result.get("intent", "default")
            reply = result.get("reply", "").strip()
            if reply == "-":
                return

            # 5. 保存上下文
            save_context(mem, user_msg, reply)
            if intent == "price":
                increment_bargain_count_db(chat_id, self.settings.db_path)
                logger.info("议价轮次+1")

            # 6. 模拟人工延迟
            if self.settings.simulate_human_typing:
                delay = min(len(reply) * random.uniform(0.1, 0.3), 10.0)
                await asyncio.sleep(delay)

            # 7. 发送回复（失败则暂存队列）
            try:
                await self._send_message(ws, chat_id, to_id, myid, reply)
                logger.info(f"回复发送成功: {reply}")
            except Exception as e:
                logger.error(f"发送失败，存入待发送队列: {e}")
                self.pending_replies[chat_id] = (to_id, reply)

        except Exception as e:
            logger.error(f"生成回复异常: {e}")

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

    async def flush_pending(self, ws, myid):
        """重连后补发所有待发送消息（由 live_client 调用）"""
        if not self.pending_replies:
            return
        logger.info(f"重连后尝试补发 {len(self.pending_replies)} 条消息")
        for chat_id in list(self.pending_replies.keys()):
            to_id, text = self.pending_replies.pop(chat_id)
            try:
                await self._send_message(ws, chat_id, to_id, myid, text)
            except Exception as e:
                logger.error(f"补发失败: {e}")
                self.pending_replies[chat_id] = (to_id, text)