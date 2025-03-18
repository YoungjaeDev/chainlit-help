import os
import json
import base64
import discord
import chainlit as cl
from chainlit.discord.app import client as discord_client

from dotenv import load_dotenv
from openai import AsyncOpenAI
from openai.types.responses import ResponseOutputItemAddedEvent, ResponseOutputItemDoneEvent, ResponseOutputMessage, ResponseContentPartAddedEvent, ResponseTextDeltaEvent, ResponseFileSearchToolCall, ResponseTextDoneEvent

from literalai import LiteralClient

load_dotenv()

client = LiteralClient()
openai_client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

cl.instrument_openai()

prompt_path = os.path.join(os.getcwd(), "app/prompts/rag.json")

# We load the RAG prompt in Literal to track prompt iteration and
# enable LLM replays from Literal AI.
with open(prompt_path, "r") as f:
    rag_prompt = json.load(f)

    prompt = client.api.get_or_create_prompt(
        name=rag_prompt["name"],
        template_messages=rag_prompt["template_messages"],
        settings=rag_prompt["settings"],
    )

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="App Ideation",
            message="What kind of application can I create with Chainlit?",
            icon="/public/idea.svg",
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
        cl.Starter(
            label="Add a text element",
            message="How to add a text source chunk to a message?",
            icon="/public/write.svg",
        ),
    ]


@cl.on_chat_start
async def on_chat_start():
    """
    Send a welcome message and set up the initial user session on chat start.
    """

    client_type = cl.user_session.get("client_type")
    cl.user_session.set("messages", prompt.format_messages())
    cl.user_session.set("settings", prompt.settings)


async def use_discord_history(limit=10):
    messages = cl.user_session.get("messages", [])
    channel: discord.abc.MessageableChannel = cl.user_session.get("discord_channel")

    if channel:
        discord_messages = [message async for message in channel.history(limit=limit)]

        # Go through last `limit` messages and remove the current message.
        for x in discord_messages[::-1][:-1]:
            messages.append(
                {
                    "role": (
                        "assistant"
                        if x.author.name == discord_client.user.name
                        else "user"
                    ),
                    "content": (
                        x.clean_content
                        if x.clean_content is not None
                        else x.channel.name
                    ),  # first message is empty
                }
            )


# Function to encode an image
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

@cl.step(name="RAG Agent", type="run")
async def rag_agent(question, images_content):
    """
    Coordinate the RAG agent flow to generate a response based on the user's question.
    """
    # Step 1 - Call LLM with tool: plan to use tool or give message.
    messages = cl.user_session.get("messages", []) or []
    messages.append(
        {
            "role": "user",
            "content": [{"type": "input_text", "text": question}, *images_content],
        }
    )

    settings = cl.user_session.get("settings", {}) or {}
    
    stream = await openai_client.responses.create(
        input=messages,
        **settings,
        tools=[{
            "type": "file_search",
            "vector_store_ids": [os.getenv("OPENAI_VECTOR_STORE_ID")],
            "max_num_results": 10
        }],
        include=["file_search_call.results"],
        stream=True
    )
    
    tools: dict[str, cl.Step] = {}
    messages: dict[str, cl.Message] = {}
    
    async for event in stream:
        if isinstance(event, ResponseOutputItemAddedEvent):
            if isinstance(event.item, ResponseFileSearchToolCall):
                step = cl.Step(name="file_search", type="tool")
                tools[event.item.id] = step
                await step.__aenter__()
                    
        elif isinstance(event, ResponseOutputItemDoneEvent):
            if isinstance(event.item, ResponseFileSearchToolCall):
                step = tools.get(event.item.id)

                if step:
                    results = [r.model_dump() for r in event.item.results]
                    step.language = "json"
                    step.input = json.dumps(event.item.queries, indent=4)
                    step.output = json.dumps(results, indent=4)
                    tools[event.item.id] = step
                    await step.__aexit__(None, None, None)
                    
        elif isinstance(event, ResponseContentPartAddedEvent):
            messages[event.item_id+str(event.content_index)] = cl.Message(content="")

        elif isinstance(event, ResponseTextDeltaEvent):
            message = messages.get(event.item_id+str(event.content_index))
            if not message:
                continue
            await message.stream_token(event.delta)
            
        elif isinstance(event, ResponseTextDoneEvent):
            message = messages.get(event.item_id+str(event.content_index))
            if message:
                await message.send()


@cl.on_message
async def main(message: cl.Message):
    """
    Main message handler for incoming user messages.
    """
    images_content = []
    if message.elements:
        images = [file for file in message.elements if "image" in file.mime]

        # Only process the first 3 images
        images = images[:3]

        images_content = [
            {
                "type": "input_image",
                "image_url": f"data:{image.mime};base64,{encode_image(image.path)}"
            }
            for image in images
        ]
        print(images_content)
    # The user session resets on every Discord message. Add previous chat messages manually.
    await use_discord_history()

    await rag_agent(message.content, images_content)
