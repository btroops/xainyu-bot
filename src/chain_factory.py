from langchain_core.runnables import RunnableLambda, RunnableBranch
from src.agents.classifier import build_classify_chain
from src.agents.price import build_price_chain
from src.agents.tech import build_tech_chain
from src.agents.default import build_default_chain

def build_reply_chain(memory, item_desc, model):
    classify_chain = build_classify_chain(model)
    price_chain = build_price_chain(memory, item_desc, model)
    tech_chain = build_tech_chain(memory, item_desc, model)
    default_chain = build_default_chain(memory, item_desc, model)

    branch = RunnableBranch(
        (lambda x: x.get("intent") == "no_reply", RunnableLambda(lambda x: {"intent": "no_reply", "reply": "-"})),
        (lambda x: x.get("intent") == "price", price_chain),
        (lambda x: x.get("intent") == "tech", tech_chain),
        default_chain
    )

    def classify_and_pass(x):
        intent = classify_chain.invoke(x)
        x["intent"] = intent
        return x

    # 将 item_desc 和 bargain_count 预先放入 inputs（bargain_count 已在 handler 中放入）
    def inject_item_desc(x):
        x["item_desc"] = item_desc
        return x

    chain = (
        RunnableLambda(inject_item_desc)
        | RunnableLambda(classify_and_pass)
        | branch
    )
    return chain