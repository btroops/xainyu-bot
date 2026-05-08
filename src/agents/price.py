from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from src.agents.base import load_prompt

# 缓存不同温度下的模型实例，避免重复创建连接
_temp_models = {}

def _get_temp_model(base_model: ChatOpenAI, temperature: float) -> ChatOpenAI:
    key = (base_model.model_name, base_model.openai_api_base, temperature)
    if key not in _temp_models:
        _temp_models[key] = ChatOpenAI(
            model=base_model.model_name,
            api_key=base_model.openai_api_key,
            base_url=base_model.openai_api_base,
            temperature=temperature,
        )
    return _temp_models[key]

def build_price_chain(memory, item_desc, model):
    async def dynamic_run(inputs: dict):
        bargain_count = inputs.get("bargain_count", 0)
        # 根据议价次数动态调整 temperature，上限 0.9
        temp = min(0.3 + bargain_count * 0.15, 0.9)
        dyn_model = _get_temp_model(model, temp)

        prompt = ChatPromptTemplate.from_messages([
            ("system", load_prompt("price_prompt")),
            ("human", "{input}")
        ])
        formatted = prompt.invoke({
            "input": inputs["input"],
            "history": inputs.get("history", ""),
            "item_desc": item_desc,
            "bargain_count": bargain_count
        })
        # 关键：使用异步 invoke 不阻塞事件循环
        resp = await dyn_model.ainvoke(formatted)
        return {"intent": "price", "reply": resp.content}

    return RunnableLambda(dynamic_run)