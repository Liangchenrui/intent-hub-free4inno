"""Small OpenAI-compatible LLM client used by recommendations and diagnostics."""

import json
import re

import requests

from intent_hub.config import Config


class LLMService:
    _OUTPUT_FORMATS = {
        "positive": '请严格只输出 JSON 对象，格式为 {"utterances": ["语料1", "语料2"]}。',
        "negative": '请严格只输出 JSON 对象，格式为 {"negative_samples": ["负向语料1", "负向语料2"]}。',
    }

    @classmethod
    def _render_template(cls, template: str, values: dict, polarity: str) -> str:
        """Render both the current prompts and prompts inherited from master.

        The master prompts contain ``{format_instructions}``, which used to be
        supplied as a LangChain partial variable.  The lightweight HTTP client
        does not use LangChain, so supply the equivalent instructions here.
        """
        variables = {
            **values,
            "format_instructions": cls._OUTPUT_FORMATS[polarity],
        }
        try:
            return template.format(**variables)
        except KeyError as error:
            missing = str(error.args[0])
            supported = ", ".join(sorted(variables))
            raise ValueError(
                f"提示词模板包含不支持的变量 {{{missing}}}；可用变量：{supported}"
            ) from error
        except ValueError as error:
            raise ValueError(
                "提示词模板格式错误；如需直接书写 JSON，请使用双大括号 {{ 和 }}"
            ) from error

    def _invoke(self, prompt: str):
        if not Config.LLM_API_KEY:
            raise ValueError("请先在运行环境中配置 LLM API Key")
        if Config.LLM_PROVIDER == "gemini":
            model = Config.LLM_MODEL or "gemini-pro"
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={Config.LLM_API_KEY}"
            response = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": Config.LLM_TEMPERATURE}}, timeout=120)
            response.raise_for_status()
            text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
        else:
            base = (Config.LLM_BASE_URL or "").rstrip("/")
            if not base:
                raise ValueError("请配置 LLM Base URL")
            response = requests.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {Config.LLM_API_KEY}", "Content-Type": "application/json"},
                json={"model": Config.LLM_MODEL, "temperature": Config.LLM_TEMPERATURE, "messages": [{"role": "user", "content": prompt}]},
                timeout=120,
            )
            response.raise_for_status()
            text = response.json()["choices"][0]["message"]["content"]
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
        return json.loads(cleaned)

    def recommendations(self, agent, request) -> list[str]:
        values = {
            "name": request.title if request.title is not None else agent.title,
            "description": request.text if request.text is not None else agent.text,
            "reference_utterances": request.utterances if request.utterances is not None else agent.utterances,
            "utterances": request.utterances if request.utterances is not None else agent.utterances,
            "negative_samples": request.negative_samples if request.negative_samples is not None else agent.negative_samples,
            "count": request.count,
        }
        template = Config.UTTERANCE_GENERATION_PROMPT if request.polarity == "positive" else Config.NEGATIVE_SAMPLE_GENERATION_PROMPT
        prompt = self._render_template(template, values, request.polarity)
        result = self._invoke(prompt)
        if isinstance(result, dict):
            result = result.get("utterances") or result.get("negative_samples") or result.get("items") or []
        if not isinstance(result, list):
            raise RuntimeError("LLM 未返回语料数组")
        existing = set(values["utterances"] if request.polarity == "positive" else values["negative_samples"])
        return list(dict.fromkeys(str(item).strip() for item in result if str(item).strip() and str(item).strip() not in existing))[:request.count]

    def repair(self, source, target, conflicts):
        prompt = Config.AGENT_REPAIR_PROMPT.format(
            name_a=source.title, name_b=target.title, desc_a=source.text, desc_b=target.text,
            utterances_a=source.utterances[:10], conflicts=conflicts[:10],
        )
        result = self._invoke(prompt)
        if not isinstance(result, dict):
            raise RuntimeError("LLM 未返回修复对象")
        return {
            "route_id": source.id, "route_name": source.title,
            "new_utterances": result.get("new_utterances", []),
            "negative_samples": result.get("negative_samples", []),
            "conflicting_utterances": result.get("conflicting_utterances", []),
            "rationalization": result.get("rationalization", ""),
        }
