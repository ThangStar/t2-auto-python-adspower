import base64
import os
from google import genai
from google.genai import types


def gemini_post_generate(content, apikey, model='gemini-2.5-pro'):
    print("generate content..")
    client = genai.Client(
        api_key=apikey,
    )

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_text(text=content),
            ],
        ),
    ]
    tools = [
        types.Tool(googleSearch=types.GoogleSearch(
        )),
    ]
    generate_content_config = types.GenerateContentConfig(
        thinking_config = types.ThinkingConfig(
            thinking_budget=-1,
        ),
        tools=tools,
        system_instruction=[
            types.Part.from_text(text=f"""Bạn là AI tạo bài đăng Facebook, chỉ gửi kết quả cuối cùng, không giải thích thêm, có hashtag đầy đủ
Bối cảnh: {content}
Ngôn ngữ: tiếng anh
Cấu trúc: nội dung và hashtag"""),
        ],
    )

    content = client.models.generate_content(
        model=model,
        contents=contents,
        config=generate_content_config,
    )
    return content.text



