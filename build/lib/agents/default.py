from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from src.agents.base import load_prompt

def build_default_chain(memory, item_desc, model):
    def default_run(inputs: dict):
        prompt = ChatPromptTemplate.from_messages([
            ("system", load_prompt("default_prompt").format(item_desc=item_desc)),
            ("placeholder", "{history}"),
            ("human", "{input}")
        ])
        formatted = prompt.invoke({
            "input": inputs["input"],
            "history": inputs.get("history", [])
        })
        resp = model.invoke(formatted)
        return {"intent": "default", "reply": resp.content}
    return RunnableLambda(default_run)