from dotenv import load_dotenv
from openai import OpenAI
import json
import os
import requests
from pypdf import PdfReader
import gradio as gr


load_dotenv(override=True)

def push(text):
    requests.post(
        "https://api.pushover.net/1/messages.json",
        data={
            "token": os.getenv("PUSHOVER_TOKEN"),
            "user": os.getenv("PUSHOVER_USER"),
            "message": text,
        }
    )


def record_user_details(email, name="Name not provided", notes="not provided"):
    push(f"Recording {name} with email {email} and notes {notes}")
    return {"recorded": "ok"}

def record_unknown_question(question):
    push(f"Recording {question}")
    return {"recorded": "ok"}

record_user_details_json = {
    "name": "record_user_details",
    "description": "Use this tool to record that a user is interested in being in touch and provided an email address",
    "parameters": {
        "type": "object",
        "properties": {
            "email": {
                "type": "string",
                "description": "The email address of this user"
            },
            "name": {
                "type": "string",
                "description": "The user's name, if they provided it"
            }
            ,
            "notes": {
                "type": "string",
                "description": "Any additional information about the conversation that's worth recording to give context"
            }
        },
        "required": ["email"],
        "additionalProperties": False
    }
}

record_unknown_question_json = {
    "name": "record_unknown_question",
    "description": "Always use this tool to record any question that couldn't be answered as you didn't know the answer",
    "parameters": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The question that couldn't be answered"
            },
        },
        "required": ["question"],
        "additionalProperties": False
    }
}

tools = [{"type": "function", "function": record_user_details_json},
        {"type": "function", "function": record_unknown_question_json}]


class Me:
    """
    Represents a conversational agent for Poornima Tom, powered by OpenAI LLM.
    Loads profile and summary data, manages chat interactions, and handles tool calls.
    """
    def __init__(self):
        """
        Initializes the Me agent with OpenAI client, name, LinkedIn profile, and summary.
        Loads profile data from PDF and summary from text file.
        Raises:
            FileNotFoundError: If profile or summary files are missing.
            Exception: For any unexpected errors during initialization.
        """
        try:
            self.openai = OpenAI()
            self.name = "Poornima Tom"
            reader = PdfReader("me/linkedin.pdf")
            self.linkedin = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    self.linkedin += text
            with open("me/summary.txt", "r", encoding="utf-8") as f:
                self.summary = f.read()
        except FileNotFoundError as e:
            print(f"Error: {e}. Please ensure profile and summary files exist.")
            self.linkedin = ""
            self.summary = ""
        except Exception as e:
            print(f"Unexpected error during initialization: {e}")
            self.linkedin = ""
            self.summary = ""

    def system_prompt(self):
        """
        Constructs the system prompt for the OpenAI LLM, including agent instructions,
        summary, and LinkedIn profile.
        Returns:
            str: The full system prompt for the chat session.
        """
        # Build prompt with context and instructions
        system_prompt = (
            f"You are acting as {self.name}. You are answering questions on {self.name}'s website, "
            "particularly questions related to {self.name}'s career, background, skills and experience. "
            "Your responsibility is to represent {self.name} for interactions on the website as faithfully as possible. "
            "You are given a summary of {self.name}'s background and LinkedIn profile which you can use to answer questions. "
            "Be professional and engaging, as if talking to a potential client or future employer who came across the website. "
            "If you don't know the answer to any question, use your record_unknown_question tool to record the question that you couldn't answer, even if it's about something trivial or unrelated to career. "
            "If the user is engaging in discussion, try to steer them towards getting in touch via email; ask for their email and record it using your record_user_details tool. "
        )
        system_prompt += f"\n\n## Summary:\n{self.summary}\n\n## LinkedIn Profile:\n{self.linkedin}\n\n"
        system_prompt += f"With this context, please chat with the user, always staying in character as {self.name}."
        return system_prompt

    def chat(self, message, history):
        """
        Handles the chat interaction with the user, sending messages to OpenAI LLM and processing tool calls.
        Args:
            message (str): The user's message.
            history (list): List of previous chat messages.
        Returns:
            str: The final response from the LLM.
        """
        # Prepare message history for LLM
        messages = [
            {"role": "system", "content": self.system_prompt()}
        ] + history + [{"role": "user", "content": message}]
        done = False
        while not done:
            try:
                response = self.openai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=tools
                )
            except Exception as e:
                print(f"Error communicating with OpenAI: {e}")
                return "Sorry, there was an error processing your request."
            if response.choices[0].finish_reason == "tool_calls":
                message = response.choices[0].message
                tool_calls = message.tool_calls
                results = self.handle_tool_call(tool_calls)
                messages.append(message)
                messages.extend(results)
            else:
                done = True
        return response.choices[0].message.content

    def handle_tool_call(self, tool_calls):
        """
        Processes tool calls requested by the LLM, executes corresponding functions, and returns results.
        Args:
            tool_calls (list): List of tool call objects from the LLM.
        Returns:
            list: Results of tool executions formatted for chat history.
        """
        results = []
        for tool_call in tool_calls:
            try:
                tool_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                print(f"Tool called: {tool_name}", flush=True)
                tool = globals().get(tool_name)
                result = tool(**arguments) if tool else {}
                results.append({"role": "tool", "content": json.dumps(result), "tool_call_id": tool_call.id})
            except Exception as e:
                print(f"Error handling tool call {tool_call}: {e}")
                results.append({"role": "tool", "content": json.dumps({"error": str(e)}), "tool_call_id": getattr(tool_call, 'id', None)})
        return results

if __name__ == "__main__":
    me = Me()
    gr.ChatInterface(
        me.chat,
        type="messages",
        title="Welcome!",
        description="Hi! I'm Poornima Tom. Ask me anything about my career, background, or experience."
    ).launch()


