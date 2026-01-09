# services/retriever/agent/tools/base.py
import os
from typing import Any
from abc import ABC, abstractmethod
from pydantic import BaseModel, ConfigDict
from openai import OpenAI


class Tool(ABC, BaseModel):
    name: str
    description: str
    arg: str

    def model_post_init(self, __context: Any) -> None:
        self.name = self.name.lower().replace(' ', '_')
        self.description = self.description.lower()
        self.arg = self.arg.lower()

    @abstractmethod
    def run(self, prompt: str) -> str:
        pass

    def get_tool_description(self):
        return f"Tool: {self.name}\nDescription: {self.description}\nArg: {self.arg}\n"

    def to_function_schema(self):
        """Convert tool to OpenAI function calling format"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": self.arg
                        }
                    },
                    "required": ["prompt"]
                }
            }
        }


class LLMTool(Tool):
    client: Any = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.client is None:
            self.client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
