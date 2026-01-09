from typing import Literal, Optional, Tuple
from openai import OpenAI
from config import settings
from .tools.query_builder import QueryBuilderTool
from .tools.safety_guard import SafetyGuardTool
from .tools.internet_search import AresInternetTool



class Orchestrator:

    CONVERSATION_SYSTEM_PROMPT = """You are a helpful assistant specialized in helping users search for live music events in a Neo4j database.

Your role:
1. Help users find live music events by understanding their preferences (date, location, genre, artist, venue, etc.)
2. When a query is executed, provide clear, natural language responses based on the results
3. If results are empty, suggest alternative search criteria
4. Be conversational, friendly, and helpful

Database Schema:
{schema}
"""

    OUT_OF_SCOPE_RESPONSE = """I'm a live music events search assistant. I help you find concerts, shows, and performances.

I can help you search for events by:
- Date and time (e.g., "events this weekend", "shows on Friday night")
- Location (e.g., "concerts in Berlin", "events in NYC")
- Genre (e.g., "jazz concerts", "rock shows")
- Artist or band name
- Venue name
- Any combination of the above

How can I help you find live music events today?"""

    UNSAFE_CONTENT_RESPONSE = """I'm sorry, but I can't process that request. I'm designed to help you find live music events in a safe and helpful way.

Please feel free to ask me about concerts, shows, and performances, and I'll be happy to help!"""


    def __init__(self, schema: str):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.schema = schema
        self._conversation_prompt = self.CONVERSATION_SYSTEM_PROMPT.format(schema=schema)
        self.query_builder_tool = QueryBuilderTool(schema=schema)
        self.safety_guard_tool = SafetyGuardTool()
        self.internet_search_tool = AresInternetTool()  # TODO

        self.tools = {
            self.query_builder_tool.name: self.query_builder_tool,
            self.internet_search_tool.name: self.internet_search_tool,
        }
        self.function_schemas = [tool.to_function_schema() for tool in self.tools.values()]


    def decide_action(
        self,
        user_message: str,
        conversation_history: Optional[list] = None
    ) -> Literal["QUERY_DB", "NEEDS_INFO", "OUT_OF_SCOPE", "BYE_MESSAGE", "UNSAFE_INPUT"]:
        # First, validate input safety using LlamaGuard
        input_safety = self.safety_guard_tool.validate_input_safety(user_message)
        if input_safety.get("verdict") == "unsafe":
            return "UNSAFE_INPUT"

        history_context = ""
        if conversation_history:
            history_context = "\n\nConversation history:\n"
            for msg in conversation_history:
                history_context += f"{msg.role}: {msg.content}\n"

        decision_prompt = f"""You are analyzing a user message for a live music events search assistant.
{history_context}
Current user message: "{user_message}"

Determine the intent and respond with ONE of these options:
1. "OUT_OF_SCOPE" - If the message is NOT about searching for live music events
2. "NEEDS_INFO" - If the message IS about live music events but is missing critical information
3. "QUERY_DB" - If the message IS about live music events AND has enough information to search
4. "BYE_MESSAGE" - If the user is ending the conversation (e.g., saying goodbye, thanks, that's all, etc.)

Important: Consider conversation history. If user says "same dates" or "there", look at history.

Respond with ONLY one word: OUT_OF_SCOPE, NEEDS_INFO, QUERY_DB or BYE_MESSAGE"""


        response = self.client.chat.completions.create(
            model=settings.conversation_model,
            messages=[{"role": "user", "content": decision_prompt}],
            temperature=0,
            max_tokens=20,
        )

        decision = response.choices[0].message.content.strip().upper()

        if "OUT_OF_SCOPE" in decision:
            return "OUT_OF_SCOPE"
        elif "NEEDS_INFO" in decision:
            return "NEEDS_INFO"
        elif "BYE_MESSAGE" in decision:
            return "BYE_MESSAGE"
        else:
            return "QUERY_DB"

    def execute_query(self, user_message: str) -> tuple[Optional[str], Optional[list]]:
        result_json = self.query_builder_tool.run(user_message)
        import json
        result_data = json.loads(result_json)

        if result_data.get("status") == "error":
            raise ValueError(result_data.get("error", "Query execution failed"))

        cypher = result_data.get("cypher")
        results = result_data.get("results", [])

        return cypher, results


    def generate_response(
        self,
        action: str,
        user_message: str,
        conversation_history: Optional[list] = None,
        cypher: Optional[str] = None,
        results: Optional[list] = None
    ) -> Tuple[str, Optional[str], Optional[list], bool, bool]:
        if action == "UNSAFE_INPUT":
            return (
                self.UNSAFE_CONTENT_RESPONSE,
                None,
                None,
                False,
                False
            )

        if action == "OUT_OF_SCOPE":
            return (
                self.OUT_OF_SCOPE_RESPONSE,
                None,
                None,
                False,
                False
            )

        elif action == "NEEDS_INFO":
            guidance_prompt = f"""The user wants to search for live music events but their request is missing minimum information to perform a query.

User message: "{user_message}"

Provide a friendly, helpful response that:
1. Acknowledges their interest in finding events
2. Asks for the missing information (date, location, genre, artist, or venue)
3. Gives examples of what information would be helpful

Be conversational and helpful."""

            guidance_response = self.client.chat.completions.create(
                model=settings.conversation_model,
                messages=[{"role": "user", "content": guidance_prompt}],
                temperature=0.7,
            )

            return (
                guidance_response.choices[0].message.content.strip(),
                None,
                None,
                False,
                True
            )

        elif action == "QUERY_DB":
            messages = [{"role": "system", "content": self._conversation_prompt}]
            if conversation_history:
                for msg in conversation_history:
                    messages.append({"role": msg.role, "content": msg.content})
            messages.append({"role": "user", "content": user_message})

            results_summary = f"Query executed successfully. Found {len(results) if results else 0} event(s)."
            if results:
                sample_results = results[:5] if len(results) > 5 else results
                results_summary += f"\n\nEvent details:\n{str(sample_results)}"
                if len(results) > 5:
                    results_summary += f"\n\n(Showing 5 of {len(results)} total events)"
            else:
                results_summary += "\n\nNo events found matching your criteria. Try adjusting your search."

            messages.append({
                "role": "assistant",
                "content": f"I searched the database and found these results:\n{results_summary}",
            })

            response = self.client.chat.completions.create(
                model=settings.conversation_model,
                messages=messages,
                temperature=0.7,
            )

            response_text = response.choices[0].message.content.strip()

            # Validate output safety
            output_safety = self.safety_guard_tool.validate_output_safety(response_text)
            if output_safety.get("verdict") == "unsafe":
                response_text = "I found some events, but I need to be more careful with how I present them. Could you rephrase your question?"

            return (
                response_text,
                cypher,
                results,
                True,
                False
            )

        elif action == "BYE_MESSAGE":
            messages = [{"role": "system", "content": self._conversation_prompt}]
            if conversation_history:
                for msg in conversation_history:
                    messages.append({"role": msg.role, "content": msg.content})
            messages.append({"role": "user", "content": user_message})

            goodbye_prompt = """The user is ending the conversation. Generate a warm, personal goodbye message that:

1. Thanks them for using the service
2. References specific details from our conversation if available (e.g., the type of events they searched for, location, genre, etc.) to make it personal
3. Encourages them to:
   - Come back anytime to search for more events
   - Visit regularly to discover new concerts and shows
   - Enjoy the live music experience
   - Spread the word about amazing events they discover
4. Wishes them well at the shows

Be warm, friendly, and conversational. If you know what kind of events they were interested in, mention it naturally. Keep it concise but heartfelt."""

            messages.append({
                "role": "user",
                "content": goodbye_prompt
            })

            goodbye_response = self.client.chat.completions.create(
                model=settings.conversation_model,
                messages=messages,
                temperature=0.8,
            )

            response_text = goodbye_response.choices[0].message.content.strip()

            # Validate output safety
            output_safety = self.safety_guard_tool.validate_output_safety(response_text)
            if output_safety.get("verdict") == "unsafe":
                response_text = "Thank you for using our live music events search! Come back anytime to discover more great shows!"

            return (
                response_text,
                None,
                None,
                False,
                False
            )

        return ("I'm not sure how to help with that.", None, None, False, False)
