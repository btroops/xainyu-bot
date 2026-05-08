from langchain_core.runnables import RunnableLambda, RunnableBranch
from src.agents.classifier import build_classify_chain
from src.agents.price import build_price_chain
from src.agents.tech import build_tech_chain
from src.agents.default import build_default_chain
from langchain_core.runnables import RunnableBranch, RunnableLambda

def build_reply_chain(memory, item_desc, model):
    classify_chain = build_classify_chain(model)
    price_chain = build_price_chain(memory, item_desc, model)
    tech_chain = build_tech_chain(memory, item_desc, model)
    default_chain = build_default_chain(memory, item_desc, model)

    # -------------------------- 分支函数：带打印日志 --------------------------
    def no_reply_branch(x):
        print("\n" + "="*50)
        print("📌 分支选择：无需回复 (no_reply)")
        print("="*50)
        return {"intent": "no_reply", "reply": "-"}

    # -------------------------- 核心处理函数：带打印日志 --------------------------
    def classify_and_pass(x):
        print("\n" + "="*50)
        print("📝 步骤2：意图分类处理")
        print(f"分类前输入: {x}")
        
        # 执行意图分类
        intent = classify_chain.invoke(x)
        x["intent"] = intent
        
        print(f"✅ 识别用户意图: {intent}")
        print(f"分类后输出: {x}")
        print("="*50)
        return x

    def inject_item_desc(x):
        print("\n" + "="*50)
        print("📝 步骤1：注入商品描述信息")
        print(f"注入前输入: {x}")
        
        # 注入商品描述
        x["item_desc"] = item_desc
        
        print(f"注入后输出: {x}")
        print("="*50)
        return x

    # 定义分支路由
    branch = RunnableBranch(
        (lambda x: x.get("intent") == "no_reply", RunnableLambda(no_reply_branch)),
        (lambda x: x.get("intent") == "price", RunnableLambda(lambda x: (print("\n📌 分支选择：价格咨询 (price)"), price_chain.invoke(x))[1])),
        (lambda x: x.get("intent") == "tech", RunnableLambda(lambda x: (print("\n📌 分支选择：技术咨询 (tech)"), tech_chain.invoke(x))[1])),
        RunnableLambda(lambda x: (print("\n📌 分支选择：默认回复 (default)"), default_chain.invoke(x))[1])
    )

    # 组装完整链条
    chain = (
        RunnableLambda(inject_item_desc)
        | RunnableLambda(classify_and_pass)
        | branch
    )
    
    print("\n✅ 回复链构建完成！准备接收用户消息...")
    return chain