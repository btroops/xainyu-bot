import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from src.agents.base import load_prompt

def build_classify_chain(model):
    prompt = ChatPromptTemplate.from_messages([
        ("system", load_prompt("classify_prompt")),
        ("human", "{input}")
    ])
    llm_chain = prompt | model | (lambda x: x.content.strip())

    def rule_match(x: dict):
        msg = x["input"]
        clean = re.sub(r'[^\w\u4e00-\u9fa5]', '', msg)
        tech_words = ['参数','规格','型号','连接','对比','功能']
        price_words = ['便宜','价格','多少钱','砍价','少点','优惠']
        if any(w in clean for w in tech_words):
            return "tech"
        if any(w in clean for w in price_words):
            return "price"
        return llm_chain.invoke(x)

    return RunnableLambda(rule_match)