from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from src.agents.base import load_prompt
# 全局搜索模型实例
_search_model = None

def build_tech_chain(memory, item_desc, model):
    global _search_model
    search_model = ChatOpenAI(
        model=model.model_name,
        api_key=model.openai_api_key,
        base_url=model.openai_api_base,
        temperature=0.4,
        model_kwargs={"enable_search": True}
    )

    async def tech_run(inputs: dict):
        prompt = ChatPromptTemplate.from_messages([
            ("system", load_prompt("tech_prompt")),
            ("human", "{input}")
        ])
        formatted = prompt.invoke({
            "input": inputs["input"],
            "history": inputs.get("history", ""),
            "item_desc": item_desc
        })
        resp = await search_model.ainvoke(formatted)
        return {"intent": "tech", "reply": resp.content}

    return RunnableLambda(tech_run)