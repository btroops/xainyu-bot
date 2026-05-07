import os, sqlite3
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.messages import SystemMessage

class XianyuMemory(ConversationBufferMemory):
    bargain_count: int = 0

    def load_memory_variables(self, inputs):
        vars = super().load_memory_variables(inputs)
        history = vars.get(self.memory_key, [])
        if self.bargain_count > 0:
            history.append(SystemMessage(content=f"议价次数: {self.bargain_count}"))
        vars[self.memory_key] = history
        return vars

def get_memory(chat_id: str, db_path: str) -> XianyuMemory:
    # 确保目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    message_history = SQLChatMessageHistory(
        session_id=chat_id,
        connection_string=f"sqlite:///{db_path}"
    )
    return XianyuMemory(
        chat_memory=message_history,
        memory_key="history",
        input_key="input",
        output_key="output",
    )

def save_context(memory: XianyuMemory, user_msg: str, assistant_msg: str):
    if user_msg and assistant_msg:
        memory.save_context({"input": user_msg}, {"output": assistant_msg})
    elif user_msg:
        memory.chat_memory.add_user_message(user_msg)
    elif assistant_msg:
        memory.chat_memory.add_ai_message(assistant_msg)

def init_bargain_table(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS bargain_counts "
        "(chat_id TEXT PRIMARY KEY, count INTEGER DEFAULT 0)"
    )
    conn.commit()
    conn.close()

def increment_bargain_count_db(chat_id: str, db_path: str):
    init_bargain_table(db_path)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO bargain_counts (chat_id, count) VALUES (?,1) "
        "ON CONFLICT(chat_id) DO UPDATE SET count=count+1",
        (chat_id,)
    )
    conn.commit()
    conn.close()

def get_bargain_count_db(chat_id: str, db_path: str) -> int:
    init_bargain_table(db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT count FROM bargain_counts WHERE chat_id=?", (chat_id,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else 0