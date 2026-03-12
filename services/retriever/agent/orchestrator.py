from typing import Literal, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time
from loguru import logger
from agent.utils.llm_utils import get_openai_client
from config import settings
from .tools.query_builder import QueryBuilderTool
from .tools.safety_guard import SafetyGuardTool
from .tools.location import LocationTool
from .tools.internet_search import InternetSearchTool
from .utils.llm_utils import chat_completion_with_retry
DECISION_PROMPT = """You are analyzing a user message for a live music events search assistant.

{history_context}

Current user message: "{user_message}"

Classify the intent as ONE of:
1. OUT_OF_SCOPE: Not about live music events (weather, directions, bookings, restaurants, general questions)
2. NEEDS_INFO: About music but missing critical constraints (no location/date/artist/venue)
3. QUERY_DB: Has specific constraints OR references previous context that provides constraints
4. BYE_MESSAGE: Farewell message (goodbye, thanks, bye, etc.)

IMPORTANT RULES:
- Artist-specific queries → QUERY_DB (even without date/location)
  Example: "Radiohead concerts" → QUERY_DB
- Venue-specific queries → QUERY_DB (even without dates)
  Example: "events at Berghain" → QUERY_DB
- Context-dependent follow-ups → QUERY_DB if previous context provides constraints
  Example: Previous: "concerts in Berlin", Current: "what about tomorrow?" → QUERY_DB
  Example: Previous: "find jazz events", Current: "in that city" → NEEDS_INFO (no city mentioned)
- Pronoun references → Resolve using conversation history
  Example: "that venue", "those artists", "tomorrow" (relative to conversation)
- Booking/tickets/directions → OUT_OF_SCOPE (we only search, not book)

CONTEXT RESOLUTION:
- Check conversation history for missing information
- If history provides the constraint, classify as QUERY_DB
- If history doesn't provide enough info, classify as NEEDS_INFO

Respond with ONLY one word: OUT_OF_SCOPE, NEEDS_INFO, QUERY_DB, or BYE_MESSAGE"""

OUT_OF_SCOPE_PROMPT = """You are a live music events search assistant. The user sent a message that is outside your scope.

Respond politely explaining you only help with live music event searches.
Mention what you CAN help with: finding events by date, location, genre, artist, or venue.
End with a friendly invitation to ask about live music events.
Reply in the same language as the user message.

User message: "{user_message}"

Keep your response concise and friendly."""

UNSAFE_CONTENT_PROMPT = """You are a live music events search assistant. The user sent a message that cannot be processed safely.

Respond briefly and politely. Explain you can't process that request.
Invite them to ask about concerts, shows, or performances instead.
Reply in the same language as the user message.

User message: "{user_message}"

Keep your response concise."""

REACT_SYSTEM_PROMPT = """You are a live music events search assistant. You help users find concerts, shows, and performances using a Neo4j database.

You operate in a ReAct loop: reason step by step, take an action if needed, observe the result, and repeat until you have a Final Answer.

## Available tools

- **search_events**: Search the Neo4j database for live music events.
  Input: a natural language description of what to search for (e.g. "jazz concerts in Berlin next weekend").
- **search_nearby**: Search for events near the user's location. Only available when the user's location is known.
  Input: a natural language description of what to search for (e.g. "jazz concerts nearby").

## Response format

For a tool call respond EXACTLY like this (no extra text before or after):
Thought: <your reasoning about what to do next>
Action: search_events
Action Input: <natural language query>

For the final answer respond EXACTLY like this:
Thought: <your reasoning about the final response>
Final Answer: <your response to the user>

## Guidelines

- Use `search_events` when the user wants live music events with enough constraints (artist, venue, location, date, genre, or any combination).
- Use `search_nearby` when the user asks for events "near me", "nearby", "around me", "close to me", etc. AND the user's location is available. This tool progressively expands the search radius up to 30 km until enough events are found.
- If the user asks for nearby events but their location is NOT available, give a **Final Answer** asking them to share their location or specify a city.
- If the query lacks enough information (no location, date, artist, or venue), give a **Final Answer** asking for the missing detail.
- If the query is completely unrelated to live music (weather, restaurants, directions, etc.), give a **Final Answer** politely explaining you only help with live music event searches.
- If `search_events` returns no results, you may try one broader or rephrased search before giving up. After that, give a **Final Answer** with helpful suggestions.
- If it is a farewell/goodbye message, give a warm **Final Answer**.
- Never fabricate events. Only report what the tools actually return.
- Events from the database are labeled `source: "verified"` and events from internet search are labeled `source: "internet"`. When presenting results, clearly distinguish verified events from internet-sourced ones.
- Be concise, friendly, and helpful.

## Database schema

{schema}"""


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

    def __init__(self, schema: str):
        self.client = get_openai_client()
        self.schema = schema
        self._conversation_prompt = self.CONVERSATION_SYSTEM_PROMPT.format(
            schema=schema
        )
        self.query_builder_tool = QueryBuilderTool(schema=schema)
        self.safety_guard_tool = SafetyGuardTool()
        self.location_tool = LocationTool()
        self.internet_search_tool = InternetSearchTool()

    def _generate_fallback_response(self, prompt: str, user_message: str = "") -> str:
        """Call the LLM to produce a fallback response in the user's language."""
        response = chat_completion_with_retry(
            self.client,
            model=settings.conversation_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt.format(user_message=user_message),
                }
            ],
            temperature=settings.llm_temperature_conversation,
        )
        return response.choices[0].message.content.strip()

    def decide_action(
        self, user_message: str, conversation_history: Optional[list] = None
    ) -> Literal[
        "QUERY_DB", "NEEDS_INFO", "OUT_OF_SCOPE", "BYE_MESSAGE", "UNSAFE_INPUT"
    ]:

        if self.safety_guard_tool.detect_injection(user_message):
            return "UNSAFE_INPUT"

        if self._check_safety(user_message).get("verdict") == "unsafe":
            return "UNSAFE_INPUT"

        history_context = ""
        if conversation_history:
            history_context = "\n\nConversation history:\n"
            for msg in conversation_history:
                role = msg.role if hasattr(msg, "role") else msg["role"]
                content = msg.content if hasattr(msg, "content") else msg["content"]
                history_context += f"{role}: {content}\n"

        decision_prompt = DECISION_PROMPT.format(
            history_context=history_context, user_message=user_message
        )

        response = self._call_decision_llm(decision_prompt)

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
        results: Optional[list] = None,
    ) -> Tuple[str, Optional[str], Optional[list], bool, bool]:
        if action == "UNSAFE_INPUT":
            return (
                self._generate_fallback_response(UNSAFE_CONTENT_PROMPT, user_message),
                None,
                None,
                False,
                False,
            )

        if action == "OUT_OF_SCOPE":
            return (
                self._generate_fallback_response(OUT_OF_SCOPE_PROMPT, user_message),
                None,
                None,
                False,
                False,
            )

        elif action == "NEEDS_INFO":
            guidance_prompt = f"""The user wants to search for live music events but their request is missing minimum information to perform a query.

User message: "{user_message}"

Provide a friendly, helpful response that:
1. Acknowledges their interest in finding events
2. Asks for the missing information (date, location, genre, artist, or venue)
3. Gives examples of what information would be helpful

Be conversational and helpful."""

            guidance_response = chat_completion_with_retry(
                self.client,
                model=settings.conversation_model,
                messages=[{"role": "user", "content": guidance_prompt}],
                temperature=settings.llm_temperature_conversation,
            )

            return (
                guidance_response.choices[0].message.content.strip(),
                None,
                None,
                False,
                True,
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
                if len(results) > settings.results_preview_limit:
                    results_summary += f"\n\n(Showing 5 of {len(results)} total events)"
            else:
                results_summary += "\n\nNo events found matching your criteria. Try adjusting your search."

            messages.append(
                {
                    "role": "assistant",
                    "content": f"I searched the database and found these results:\n{results_summary}",
                }
            )

            response = chat_completion_with_retry(
                self.client,
                model=settings.conversation_model,
                messages=messages,
                temperature=settings.llm_temperature_conversation,
            )

            response_text = response.choices[0].message.content.strip()

            # Optionally validate output safety (disabled by default for performance)
            if settings.enable_output_safety_check:
                output_safety = self.safety_guard_tool.validate_output_safety(response_text)
                if output_safety.get("verdict") == "unsafe":
                    response_text = "I found some events, but I need to be more careful with how I present them. Could you rephrase your question?"

            return (response_text, cypher, results, True, False)

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
   - Give feedback and suggestions to laiive experience in this same chat.
4. Wishes them well at the shows

Be warm, friendly, and conversational. If you know what kind of events they were interested in, mention it naturally. Keep it concise but heartfelt."""

            messages.append({"role": "user", "content": goodbye_prompt})

            goodbye_response = chat_completion_with_retry(
                self.client,
                model=settings.conversation_model,
                messages=messages,
                temperature=settings.llm_temperature_goodbye,
            )

            response_text = goodbye_response.choices[0].message.content.strip()

            # Optionally validate output safety (disabled by default for performance)
            if settings.enable_output_safety_check:
                output_safety = self.safety_guard_tool.validate_output_safety(response_text)
                if output_safety.get("verdict") == "unsafe":
                    response_text = "Thank you for using our live music events search! Come back anytime to discover more great shows!"

            return (response_text, None, None, False, False)

        return ("I'm not sure how to help with that.", None, None, False, False)

    def run_react(
        self,
        user_message: str,
        conversation_history: Optional[list] = None,
        max_loops: Optional[int] = None,
        user_location: Optional[dict] = None,
    ) -> Tuple[str, Optional[str], Optional[list], bool, bool]:
        """ReAct agent loop: Thought → Action → Observation × n → Final Answer.

        Args:
            user_location: Optional dict with keys latitude, longitude, and optionally city.

        Returns: (response_text, cypher, results, used_query, needs_more_info)
        """
        if max_loops is None:
            max_loops = settings.react_max_loops

        # Safety checks before entering the loop
        if self.safety_guard_tool.detect_injection(user_message):
            return (
                self._generate_fallback_response(UNSAFE_CONTENT_PROMPT, user_message),
                None,
                None,
                False,
                False,
            )
        if self._check_safety(user_message).get("verdict") == "unsafe":
            return (
                self._generate_fallback_response(UNSAFE_CONTENT_PROMPT, user_message),
                None,
                None,
                False,
                False,
            )

        system_prompt = REACT_SYSTEM_PROMPT.format(schema=self.schema)

        # Add location context to the system prompt when available
        if user_location:
            location_note = (
                f"\n\n## User location\n"
                f"The user's current location is: latitude {user_location['latitude']}, "
                f"longitude {user_location['longitude']}"
            )
            if user_location.get("city"):
                location_note += f" (city: {user_location['city']})"
            location_note += (
                ".\nWhen the user asks for events 'near me', 'nearby', etc., "
                "use the `search_nearby` action."
            )
            system_prompt += location_note
        else:
            system_prompt += (
                "\n\n## User location\n"
                "The user's location is NOT available. If they ask for events "
                "'near me' or 'nearby', ask them to share their location or specify a city."
            )

        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            for msg in conversation_history:
                role = msg.role if hasattr(msg, "role") else msg["role"]
                content = msg.content if hasattr(msg, "content") else msg["content"]
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": user_message})

        cypher: Optional[str] = None
        results: Optional[list] = None
        used_query = False
        needs_more_info = False

        for loop_idx in range(max_loops):
            logger.debug(f"ReAct loop {loop_idx + 1}/{max_loops}")

            response = chat_completion_with_retry(
                self.client,
                model=settings.conversation_model,
                messages=messages,
                temperature=settings.llm_temperature_conversation,
            )

            assistant_content = response.choices[0].message.content.strip()
            messages.append({"role": "assistant", "content": assistant_content})
            logger.debug(f"ReAct assistant:\n{assistant_content}")

            # ── Final Answer ────────────────────────────────────────────────
            if "Final Answer:" in assistant_content:
                final_answer = assistant_content.split("Final Answer:", 1)[1].strip()

                if settings.enable_output_safety_check:
                    output_safety = self.safety_guard_tool.validate_output_safety(
                        final_answer
                    )
                    if output_safety.get("verdict") == "unsafe":
                        final_answer = (
                            "I found some events, but I need to be more careful "
                            "with how I present them. Could you rephrase your question?"
                        )

                if not used_query and any(
                    phrase in final_answer.lower()
                    for phrase in (
                        "could you provide",
                        "could you tell me",
                        "what location",
                        "which city",
                        "what date",
                        "more information",
                        "can you share",
                        "please specify",
                    )
                ):
                    needs_more_info = True

                return (final_answer, cypher, results, used_query, needs_more_info)

            # ── Tool call ────────────────────────────────────────────────────
            if "Action:" in assistant_content and "Action Input:" in assistant_content:
                action = ""
                action_input = ""
                for line in assistant_content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("Action:"):
                        action = stripped.split("Action:", 1)[1].strip()
                    elif stripped.startswith("Action Input:"):
                        action_input = stripped.split("Action Input:", 1)[1].strip()

                if action == "search_events" and action_input:
                    try:
                        observation, cypher, results, used_query = (
                            self._parallel_search(action_input, user_location)
                        )
                    except Exception as e:
                        observation = f"Error executing query: {e}"

                elif action == "search_nearby" and action_input:
                    if not user_location:
                        observation = (
                            "User location is not available. "
                            "Ask the user to share their location or specify a city."
                        )
                    else:
                        try:
                            explicit_radius = self.location_tool.extract_radius_km(
                                action_input
                            )
                            location_result = (
                                self.location_tool.search_with_progressive_radius(
                                    latitude=user_location["latitude"],
                                    longitude=user_location["longitude"],
                                    explicit_radius_km=explicit_radius,
                                )
                            )
                            results = location_result["results"]
                            radius_used = location_result["radius_km"]
                            used_query = True
                            count = len(results)
                            observation = (
                                f"Found {count} event(s) within {radius_used} km."
                            )
                            if results:
                                sample = results[: min(3, count)]
                                observation += (
                                    f"\nSample results:\n"
                                    + json.dumps(sample, default=str)
                                )
                        except Exception as e:
                            observation = f"Error in nearby search: {e}"

                else:
                    observation = (
                        f"Unknown action '{action}'. "
                        f"Available actions: search_events, search_nearby"
                    )

                messages.append({"role": "user", "content": f"Observation: {observation}"})
                continue

            # ── Malformed output — treat as final answer ─────────────────────
            logger.warning(
                f"ReAct loop {loop_idx + 1}: no Action or Final Answer found; "
                "treating response as Final Answer"
            )
            if settings.enable_output_safety_check:
                output_safety = self.safety_guard_tool.validate_output_safety(
                    assistant_content
                )
                if output_safety.get("verdict") == "unsafe":
                    assistant_content = (
                        "I found some events, but I need to be more careful "
                        "with how I present them. Could you rephrase your question?"
                    )
            return (assistant_content, cypher, results, used_query, needs_more_info)

        # ── Max loops reached — force a final answer ─────────────────────────
        logger.warning(f"ReAct agent reached max loops ({max_loops}), forcing final answer")
        messages.append(
            {
                "role": "user",
                "content": "Please provide your Final Answer now based on the information gathered so far.",
            }
        )
        response = chat_completion_with_retry(
            self.client,
            model=settings.conversation_model,
            messages=messages,
            temperature=settings.llm_temperature_conversation,
        )
        final_answer = response.choices[0].message.content.strip()
        if "Final Answer:" in final_answer:
            final_answer = final_answer.split("Final Answer:", 1)[1].strip()
        return (final_answer, cypher, results, used_query, needs_more_info)

    def _parallel_search(
        self,
        action_input: str,
        user_location: Optional[dict] = None,
    ) -> tuple:
        """Run knowledge-graph and internet searches in parallel.

        Returns: (observation, cypher, results, used_query)
        KG results are tagged source="verified", internet results source="internet".
        """
        # Enrich query with location context if available
        enriched_input = action_input
        if user_location and self.location_tool.is_proximity_query(action_input):
            enriched_input += (
                f" (user is at lat {user_location['latitude']}, "
                f"lon {user_location['longitude']})"
            )

        internet_enabled = (
            settings.enable_internet_search
            and bool(settings.brave_search_api_key)
        )

        kg_result_data = None
        internet_events = []

        if internet_enabled:
            with ThreadPoolExecutor(max_workers=2) as executor:
                kg_future = executor.submit(self.query_builder_tool.run, enriched_input)
                web_future = executor.submit(self.internet_search_tool.run, action_input)

                for future in as_completed([kg_future, web_future]):
                    if future is kg_future:
                        try:
                            kg_result_data = json.loads(future.result())
                        except Exception as e:
                            logger.error(f"KG search failed: {e}")
                    else:
                        try:
                            web_data = json.loads(future.result())
                            if web_data.get("status") == "success":
                                internet_events = web_data.get("results", [])
                        except Exception as e:
                            logger.error(f"Internet search failed: {e}")
        else:
            try:
                kg_result_data = json.loads(self.query_builder_tool.run(enriched_input))
            except Exception as e:
                logger.error(f"KG search failed: {e}")

        # Process KG results
        cypher = None
        kg_events = []
        used_query = False

        if kg_result_data and kg_result_data.get("status") == "success":
            cypher = kg_result_data.get("cypher")
            kg_events = kg_result_data.get("results", [])
            used_query = True
            # Tag KG results as verified
            for event in kg_events:
                event["source"] = "verified"

        # Merge: KG results first (verified), then internet results
        merged = kg_events + internet_events
        results = merged if merged else None

        # Build observation for the ReAct loop
        kg_count = len(kg_events)
        web_count = len(internet_events)
        parts = []

        if kg_result_data and kg_result_data.get("status") == "success":
            parts.append(f"{kg_count} verified event(s) from database")
        elif kg_result_data:
            parts.append(
                f"Database query failed: {kg_result_data.get('error', 'Unknown error')}"
            )

        if internet_enabled and web_count > 0:
            parts.append(f"{web_count} event(s) from internet search")
        elif internet_enabled:
            parts.append("No events found from internet search")

        observation = "Found " + ", ".join(parts) + "." if parts else "No results found."

        if merged:
            sample = merged[: min(3, len(merged))]
            observation += (
                f"\nSample results:\n" + json.dumps(sample, default=str)
            )

        return observation, cypher, merged if merged else None, used_query

    def _call_decision_llm(self, decision_prompt: str):
        start_time = time.time()
        try:
            response = chat_completion_with_retry(
                self.client,
                model=settings.conversation_model,
                messages=[{"role": "user", "content": decision_prompt}],
                temperature=settings.llm_temperature_decision,
                max_tokens=settings.decision_max_tokens,
            )
            elapsed = time.time() - start_time
            logger.debug(f"Decision LLM call completed in {elapsed:.3f}s")
            return response
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Decision LLM call failed after {elapsed:.3f}s: {e}")
            raise

    def _check_safety(self, message: str):
        start_time = time.time()
        try:
            result = self.safety_guard_tool.validate_input_safety(message)
            elapsed = time.time() - start_time
            logger.debug(f"Safety check completed in {elapsed:.3f}s")
            return result
        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"Safety check failed after {elapsed:.3f}s: {e}")
            raise
