import os
import json
import base64
import discord
import chainlit as cl
from chainlit.discord.app import client as discord_client
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_anthropic import ChatAnthropic
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from langchain_core.messages import AIMessageChunk, ToolCallChunk, ToolCall, ToolMessage
from langchain.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from dotenv import load_dotenv

from literalai import LiteralClient

load_dotenv()

# Discord limits the number of characters to 2000.
DISCORD_MAX_CHARACTERS = 2000
# 2000 characters ≈ 400 tokens
DISCORD_MAX_TOKENS = 400

lai_client = LiteralClient()


prompt_path = os.path.join(os.getcwd(), "app/prompts/rag.json")
codebase_path = os.path.join(os.getcwd(), "app/context/codebase.txt")
documentation_path = os.path.join(os.getcwd(), "app/context/documentation.txt")
cookbook_path = os.path.join(os.getcwd(), "app/context/cookbook.txt")
generate_custom_element_system_prompt_path = os.path.join(
    os.getcwd(), "app/prompts/generate_custom_element_system_prompt.txt"
)

# We load the RAG prompt in Literal to track prompt iteration and
# enable LLM replays from Literal AI.
with open(prompt_path, "r") as f:
    rag_prompt = json.load(f)
    prompt = lai_client.api.get_or_create_prompt(
        name=rag_prompt["name"],
        template_messages=rag_prompt["template_messages"],
        settings=rag_prompt["settings"],
        tools=rag_prompt["tools"],
    )

with open(codebase_path, "r") as codebase_file:
    codebase_content = codebase_file.read()

with open(documentation_path, "r") as documentation_file:
    documentation_content = documentation_file.read()


with open(cookbook_path, "r") as cookbook_file:
    cookbook_content = cookbook_file.read()

with open(generate_custom_element_system_prompt_path, "r") as f:
    generate_custom_element_system_prompt = f.read()


commands = [
    {
        "id": "GenUI",
        "icon": "palette",
        "description": "Generate a Chainlit custom element",
        "button": True,
        "persistent": True,
    },
]


@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="App Ideation",
            message="What kind of application can I create with Chainlit?",
            icon="/public/idea.svg",
        ),
        cl.Starter(
            label="Create a custom element",
            message="Create a custom element to display a Linear issue.",
            icon="/public/write.svg",
        ),
        cl.Starter(
            label="How does authentication work?",
            message="Explain the different options for authenticating users in Chainlit.",
            icon="/public/learn.svg",
        ),
        cl.Starter(
            label="Chainlit hello world",
            message="Write a Chainlit hello world app.",
            icon="/public/terminal.svg",
        ),
    ]


@cl.on_chat_start
async def on_chat_start():
    client_type = cl.user_session.get("client_type")

    langchain_prompt: ChatPromptTemplate = prompt.to_langchain_chat_prompt_template()

    messages = langchain_prompt.format_messages(
        documentation=documentation_content, codebase=codebase_content, cookbook=cookbook_content
    )

    cl.user_session.set("messages", messages)
    cl.user_session.set("settings", prompt.settings)
    cl.user_session.set("tools", prompt.tools if client_type != "discord" else None)

    if client_type == "discord":
        prompt.settings["max_tokens"] = DISCORD_MAX_TOKENS
    else:
        await cl.context.emitter.set_commands(commands)


async def use_discord_history(limit=10):
    messages = cl.user_session.get("messages", [])
    channel: discord.abc.MessageableChannel = cl.user_session.get("discord_channel")

    if channel:
        discord_messages = [message async for message in channel.history(limit=limit)]

        # Go through last `limit` messages and remove the current message.
        for x in discord_messages[::-1][:-1]:
            if x.author.name == discord_client.user.name:
                messages.append(
                    AIMessage(
                        content=x.clean_content
                        if x.clean_content is not None
                        else x.channel.name
                    )
                )
            else:
                messages.append(
                    HumanMessage(
                        content=x.clean_content
                        if x.clean_content is not None
                        else x.channel.name
                    )
                )


# Function to encode an image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


@cl.step(type="tool")
async def generate_custom_element(query: str):
    class CustomElement(BaseModel):
        name: str = Field(description="Camel case name of the custom element.")
        sourceCode: str = Field(
            description="The complete source code of the custom element. Generate this automatically based on what would be most useful in the current context."
        )
        props: str = Field(
            description="JSON string of props for the custom element. Generate reasonable default props for the sourceCode that will demonstrate the element's functionality."
        )

    llm = ChatAnthropic(
        model="claude-3-5-sonnet-latest",
        temperature=0.2,
        max_tokens=4000,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )

    llm = llm.with_structured_output(CustomElement)

    messages = [SystemMessage(content=generate_custom_element_system_prompt)]

    if previous_iteration := cl.user_session.get("previous_iteration"):
        messages.append(previous_iteration)

    messages.append(HumanMessage(content=query))

    result = await llm.ainvoke(messages)

    props = result.model_dump()

    if isinstance(props["props"], str):
        props["props"] = json.loads(props["props"])

    cl.user_session.set(
        "previous_iteration",
        AIMessage(content=f"Previous query: '{query}'\nPrevious result:\n{result.model_dump_json(indent=4)}"),
    )

    return props


async def handle_tools_calls(tool_calls: list[ToolCallChunk]):
    ai_message = AIMessage(content="", tool_calls=[])
    tool_messages: list[ToolMessage] = []

    for tool_call in tool_calls:
        if tool_call["name"] == "generate_component":
            args = json.loads(tool_call["args"])
            ai_message.tool_calls.append(
                ToolCall(name=tool_call["name"], args=args, id=tool_call["id"])
            )
            props = await generate_custom_element(**args)
            tool_messages.append(
                ToolMessage(
                    tool_call_id=tool_call["id"],
                    content=f"Do NOT repeat the details of this custom element to the user. Explain to the user how to use it in his Chainlit app if necessary. Generated component:\n{json.dumps(props, indent=4)}",
                )
            )
            custom_element = cl.CustomElement(name="ChainlitArtifact", props=props)
            await cl.Message(content="", elements=[custom_element]).send()
        else:
            raise ValueError(f"Invalid tool call {tool_call['name']}")

    return ai_message, tool_messages


@cl.step(name="Chainlit Agent", type="run")
async def chainlit_agent(question, images_content):
    messages = cl.user_session.get("messages", []) or []

    # Prepare the content with text and images
    content = question
    # Note: For multi-modal support, you'd need to modify this depending on
    # how your LLM handles images with LangChain. This is a simplified version.
    if images_content:
        # This approach may need to be adjusted based on the LLM's specific requirements
        image_descriptions = [f"[Image {i + 1}]" for i in range(len(images_content))]
        content = f"{content}\n{' '.join(image_descriptions)}"

    # Add the user message
    messages.append(HumanMessage(content=content))
    cl.user_session.set("messages", messages)

    settings = cl.user_session.get("settings", {}) or {}
    tools = cl.user_session.get("tools", [])

    llm = ChatGoogleGenerativeAI(
        **settings,
        timeout=None,
    )
    if tools:
        llm = llm.bind_tools(tools)

    answer_message = None
    iteration_count = 0

    while iteration_count < 2:
        tool_calls: list[ToolCallChunk] = []
        async for chunk in llm.astream(
            messages, config={"callbacks": [cl.LangchainCallbackHandler()]}
        ):
            if isinstance(chunk, AIMessageChunk) and chunk.tool_call_chunks:
                tool_calls += chunk.tool_call_chunks
            elif chunk.content:
                if answer_message is None:
                    answer_message = cl.Message("")
                # Gemini Flash 2.0 tends to start code blocks on existing lines, which breaks markdown formatting
                if "```" in chunk.content:
                    chunk.content = chunk.content.replace("```", "\n```")
                await answer_message.stream_token(chunk.content)

        if tool_calls:
            ai_message, tool_messages = await handle_tools_calls(tool_calls)
            messages.append(ai_message)
            messages += tool_messages
            iteration_count += 1
        elif answer_message:
            # Add assistant's response to the message history
            messages.append(AIMessage(content=answer_message.content))
            await answer_message.send()

            # Handle Discord's character limit
            if (
                cl.user_session.get("client_type") == "discord"
                and len(answer_message.content) > DISCORD_MAX_CHARACTERS
            ):
                redirect_message = cl.Message(
                    content="Looks like you hit Discord's limit of 2000 characters. Please visit https://help.chainlit.io to get longer answers."
                )
                await redirect_message.send()

            break


@cl.on_message
async def main(message: cl.Message):
    if message.command == "GenUI":
        props = await generate_custom_element(message.content)
        custom_element = cl.CustomElement(name="ChainlitArtifact", props=props)
        await cl.Message(content="", elements=[custom_element]).send()
        return

    images_content = []
    if message.elements:
        images = [file for file in message.elements if "image" in file.mime]

        # Only process the first 3 images
        images = images[:3]

        images_content = [
            {
                "type": "input_image",
                "image_url": f"data:{image.mime};base64,{encode_image(image.path)}",
            }
            for image in images
        ]

    # The user session resets on every Discord message. Add previous chat messages manually.
    await use_discord_history()

    await chainlit_agent(message.content, images_content)
