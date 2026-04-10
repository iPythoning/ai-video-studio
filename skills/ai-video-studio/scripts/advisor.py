#!/usr/bin/env python3
"""
claude-advisor — Sonnet executor + Opus advisor pattern via custom tool.

Since the Anthropic API doesn't have a native `advisor` tool type,
this module implements the same pattern using a standard custom tool
plus a multi-turn orchestration loop.

Usage:
    from advisor import AdvisorClient

    client = AdvisorClient(api_key="sk-ant-...")
    result = client.run(
        "Design a marketing campaign for a new smartphone",
        executor="claude-sonnet-4-6",
        advisor="claude-opus-4-6",
        max_advisor_calls=3,
    )
    print(result.text)
    print(f"Advisor was consulted {result.advisor_calls} time(s)")
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import anthropic


ADVISOR_TOOL = {
    "name": "ask_advisor",
    "description": (
        "Consult a senior advisor (a more capable model) for strategic decisions, "
        "creative direction, quality review, or complex reasoning. The advisor has "
        "broader knowledge and deeper analytical ability. Use when you need a second "
        "opinion on important choices, not for routine tasks. Budget your uses wisely."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The strategic or creative question to ask the advisor",
            },
            "context": {
                "type": "string",
                "description": "Relevant context, constraints, or work done so far",
            },
        },
        "required": ["question"],
    },
}


@dataclass
class AdvisorResult:
    """Result from an advisor-augmented execution."""
    text: str = ""
    advisor_calls: int = 0
    advisor_log: list[dict] = field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    turns: int = 0


class AdvisorClient:
    """Orchestrates Sonnet (executor) + Opus (advisor) via tool-use loop."""

    def __init__(self, api_key: str | None = None, advisor_system: str | None = None):
        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.advisor_system = advisor_system or (
            "You are a senior strategic advisor with deep expertise. "
            "Give concise, actionable advice. Be specific and opinionated. "
            "If the approach has flaws, say so directly."
        )

    def run(
        self,
        prompt: str,
        executor: str = "claude-sonnet-4-6",
        advisor: str = "claude-opus-4-6",
        max_advisor_calls: int = 3,
        max_turns: int = 10,
        max_tokens: int = 4096,
        system: str | None = None,
        extra_tools: list | None = None,
    ) -> AdvisorResult:
        """Run a task with the executor model, giving it access to the advisor tool.

        Args:
            prompt: The user's task/question.
            executor: Model ID for the executor (fast, cheap).
            advisor: Model ID for the advisor (smart, expensive).
            max_advisor_calls: Max times executor can consult advisor.
            max_turns: Max conversation turns to prevent infinite loops.
            max_tokens: Max output tokens per turn.
            system: Optional system prompt for the executor.
            extra_tools: Additional tools the executor can use.

        Returns:
            AdvisorResult with the final text and metadata.
        """
        tools = [ADVISOR_TOOL] + (extra_tools or [])
        messages = [{"role": "user", "content": prompt}]
        result = AdvisorResult()

        for turn in range(max_turns):
            kwargs = {"model": executor, "max_tokens": max_tokens, "tools": tools, "messages": messages}
            if system:
                kwargs["system"] = system

            resp = self.client.messages.create(**kwargs)
            result.turns += 1
            result.total_input_tokens += resp.usage.input_tokens
            result.total_output_tokens += resp.usage.output_tokens

            if resp.stop_reason == "end_turn":
                for block in resp.content:
                    if hasattr(block, "text"):
                        result.text = block.text
                return result

            if resp.stop_reason == "tool_use":
                tool_calls = [b for b in resp.content if b.type == "tool_use"]
                messages.append({"role": "assistant", "content": resp.content})
                tool_results = []

                for tc in tool_calls:
                    if tc.name == "ask_advisor" and result.advisor_calls < max_advisor_calls:
                        result.advisor_calls += 1
                        q = tc.input.get("question", "")
                        ctx = tc.input.get("context", "")

                        advisor_prompt = f"Question: {q}"
                        if ctx:
                            advisor_prompt += f"\n\nContext:\n{ctx}"

                        advisor_resp = self.client.messages.create(
                            model=advisor, max_tokens=1024,
                            system=self.advisor_system,
                            messages=[{"role": "user", "content": advisor_prompt}],
                        )
                        advice = advisor_resp.content[0].text
                        result.total_input_tokens += advisor_resp.usage.input_tokens
                        result.total_output_tokens += advisor_resp.usage.output_tokens
                        result.advisor_log.append({
                            "call": result.advisor_calls,
                            "question": q,
                            "context": ctx[:200] if ctx else "",
                            "advice": advice,
                        })
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": advice,
                        })

                    elif tc.name == "ask_advisor":
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": f"Advisor budget exhausted ({max_advisor_calls} calls used). Proceed with your best judgment.",
                        })

                    else:
                        # Unknown tool — return error so executor can handle
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": tc.id,
                            "content": f"Tool '{tc.name}' not implemented in this runner.",
                            "is_error": True,
                        })

                messages.append({"role": "user", "content": tool_results})

            elif resp.stop_reason == "max_tokens":
                # Extract partial text
                for block in resp.content:
                    if hasattr(block, "text"):
                        result.text = block.text
                return result
            else:
                break

        if not result.text:
            result.text = "(max turns reached without final response)"
        return result


# ─── CLI ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Run a task with Sonnet executor + Opus advisor")
    parser.add_argument("prompt", help="Task or question for the executor")
    parser.add_argument("--executor", default="claude-sonnet-4-6")
    parser.add_argument("--advisor", default="claude-opus-4-6")
    parser.add_argument("--max-calls", type=int, default=3, help="Max advisor consultations")
    parser.add_argument("--system", default=None, help="System prompt for executor")
    parser.add_argument("--json", action="store_true", help="Output full result as JSON")
    args = parser.parse_args()

    client = AdvisorClient()
    result = client.run(
        args.prompt,
        executor=args.executor,
        advisor=args.advisor,
        max_advisor_calls=args.max_calls,
        system=args.system,
    )

    if args.json:
        print(json.dumps({
            "text": result.text,
            "advisor_calls": result.advisor_calls,
            "advisor_log": result.advisor_log,
            "total_input_tokens": result.total_input_tokens,
            "total_output_tokens": result.total_output_tokens,
            "turns": result.turns,
        }, indent=2, ensure_ascii=False))
    else:
        print(result.text)
        if result.advisor_calls > 0:
            print(f"\n--- Advisor consulted {result.advisor_calls} time(s) | "
                  f"tokens: {result.total_input_tokens}in/{result.total_output_tokens}out | "
                  f"turns: {result.turns} ---")
