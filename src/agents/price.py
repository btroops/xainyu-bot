from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from src.agents.base import load_prompt

def build_price_chain(memory, item_desc, model):
    def dynamic_run(inputs: dict):
        bargain_count = inputs.get("bargain_count", 0)
        temp = min(0.3 + bargain_count * 0.15, 0.9)
        dyn_model = ChatOpenAI(
            model=model.model_name,
            api_key=model.openai_api_key,
            base_url=model.openai_api_base,
            temperature=temp,
        )
        prompt = ChatPromptTemplate.from_messages([
            ("system", load_prompt("price_prompt")),   # 模板内包含 {history} {item_desc} {bargain_count}
            ("human", "{input}")
        ])
        formatted = prompt.invoke({
            "input": inputs["input"],
            "history": inputs.get("history", ""),
            "item_desc": item_desc,                  # 也可从 inputs 取，统一使用外层传入
            "bargain_count": bargain_count
        })
        resp = dyn_model.invoke(formatted)
        return {"intent": "price", "reply": resp.content}
    return RunnableLambda(dynamic_run)