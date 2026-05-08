import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from src.agents.base import load_prompt

def build_classify_chain(model):
    prompt = ChatPromptTemplate.from_messages([
        ("system", load_prompt("classify_prompt")),
        ("human", "{input}")
    ])
    # 构建异步 LLM 分类链
    llm_chain = prompt | model | (lambda x: x.content.strip())

    # 扩展关键字，覆盖绝大多数情形，减少 LLM 调用
    tech_keywords = [
        '参数', '规格', '型号', '连接', '对比', '功能',
        '配置', '接口', '蓝牙', '续航', '内存', '尺寸',
        '重量', '支持', '适配', '安装', '维修', '材质',
        '分辨率', '刷新率', '防水', '快充', '版本'
    ]
    price_keywords = [
        '便宜', '价格', '多少钱', '砍价', '少点', '优惠',
        '最低', '包邮', '小刀', '底价', '预算', '让利',
        '降价', '贵了', '能少吗', '便宜点'
    ]

    async def rule_match(x: dict):
        msg = x["input"]
        clean = re.sub(r'[^\w\u4e00-\u9fa5]', '', msg)
        if any(w in clean for w in tech_keywords):
            return "tech"
        if any(w in clean for w in price_keywords):
            return "price"
        # 若无匹配，走异步 LLM 分类
        return await llm_chain.ainvoke(x)

    # 显式指定异步函数，保证链调用 .ainvoke 时走协程
    return RunnableLambda(rule_match)