from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from src.agents.base import load_prompt

def build_tech_chain(memory, item_desc, model):
    search_model = ChatOpenAI(
        model=model.model_name,
        api_key=model.openai_api_key,
        base_url=model.openai_api_base,
        temperature=0.4,
        model_kwargs={"enable_search": True}
    )
    def tech_run(inputs: dict):
        prompt = ChatPromptTemplate.from_messages([
            ("system", load_prompt("tech_prompt")),   # 模板包含 {history} {item_desc}
            ("human", "{input}")
        ])
        formatted = prompt.invoke({
            "input": inputs["input"],
            "history": inputs.get("history", ""),
            "item_desc": item_desc
        })
        resp = search_model.invoke(formatted)
        return {"intent": "tech", "reply": resp.content}
    return RunnableLambda(tech_run)