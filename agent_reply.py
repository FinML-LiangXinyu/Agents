import os
from agentscope.agent import Agent
from agentscope.credential import DashScopeCredential
from agentscope.model import DashScopeChatModel
from agentscope.message import UserMsg, TextBlock
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from typing import Literal
import uvicorn
import json

# 实现字典，从字典中取出 agent
agents = {}

# 构建 fastapi 应用
app = FastAPI()

# 利用 pydantic 构造请求体，生成 agent card
class AgentCard(BaseModel):
    agent_name: str
    system_prompt: str | None = "You are a helpfull assistant."
    model_name: str

@ app.post("/agent")
async def create_agent(agentcard: AgentCard):
    # 实例化 Agent
    agent = Agent(
        name = agentcard.agent_name,
        system_prompt = agentcard.system_prompt,
        model = DashScopeChatModel(
            credential = DashScopeCredential(api_key = os.environ.get("DASHSCOPE_API_KEY")),
            model = agentcard.model_name
        )
    )
    agent.model.parameters.thinking_enable = True
    agents.update({agent.name: agent})
    return agentcard

# get 方法：从 agents 字典中取出 agent
@ app.get("/agent/{agent_name}", tags = ["agent"], description = "取出智能体")
async def get_agent(agent_name: str | None = None):
    print(agent_name)
    print(agents)
    if agent_name in agents:
        agent = agents[agent_name]
        agent_card = AgentCard(
            agent_name = agent.name,
            system_prompt = agent._system_prompt, 
            model_name = agent.model.model
        )
        return agent_card
    else:
        raise HTTPException(status_code = 404, detail = "引用了不存在的智能体名称")

# 利用 pydantic 构造请求体，生成 用户输入 供后端消费
class user_input(BaseModel):
    user_name: str | None = None
    user_input: str | None = None

# post 请求：从 /chat/stream/{agent_name} 路由返回智能体流式输出
@ app.post("/chat/stream/{agent_name}", tags = ["chat"], description = "返回流式输出")
async def conversion_with_Agent(user_input: user_input, agent_name: str | None = None):
    """智能体沟通的异步函数"""
    if agent_name in agents:
        # 将用户输入包装为 Msg 类
        agent = agents[agent_name]
        user_msg = [TextBlock(text = user_input.user_input)]
        userMsg = [UserMsg(name = user_input.user_name, content = user_msg)]
        # 构造一个异步生成器，产生流式输出
        async def stream_generator():
            async for chunk in agent.reply_stream(inputs = userMsg):
                yield json.dumps(chunk.model_dump(), ensure_ascii = False)
        # 流式响应
        return StreamingResponse(content = stream_generator())
    else:
        raise HTTPException(status_code = 404, detail = "引用了不存在的智能体名称")

# 利用 pydantic 构造结构化输出格式，判定是否属于欺诈行为
class strutured_output(BaseModel):
    isFraud: Literal["暂不怀疑", "疑似", "高度怀疑", "确定"] | None = Field(None, description = "判断是否属于欺诈信息")
    reason: str | None = Field(None, description = "解释原因")
    suggestion: str | None = Field(None, description = "建议做法")

# post 请求：从 /chat/stream/{agent_name} 路由返回智能体非流式输出
@ app.post("/chat/generate/{agent_name}", tags = ["chat"], description = "返回非流式输出")
async def conversion_with_Agent(user_input: user_input, agent_name: str | None = None):
    """智能体沟通的异步函数"""
    if agent_name in agents:
        # 将用户输入包装为 Msg 类
        agent = agents[agent_name]
        user_msg = [TextBlock(text = user_input.user_input)]
        userMsg = [UserMsg(name = user_input.user_name, content = user_msg)]
        reponse = await agent.reply(inputs = userMsg, structured_schema = strutured_output)
        return JSONResponse(json.dumps(reponse.structured_output, ensure_ascii = False))
    else:
        raise HTTPException(status_code = 404, detail = "引用了不存在的智能体名称")

if __name__ == "__main__":
    # 启动 fastapi 服务
    uvicorn.run(app = "agent_reply:app", host = "127.0.0.1", port = 8000, reload = True)