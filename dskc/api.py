import base64
import json
import re
import time

import aiohttp

from pow_solver import DeepSeekHash
from .debug import dbg


# ---------------------------------------------------------------------
# SSE parsing
# ---------------------------------------------------------------------

def parse_sse_line(line: str):
    line = line.strip()
    if not line:
        return None
    if line.startswith("event:"):
        return ("event", line.split(":", 1)[1].strip())
    if line.startswith("data:"):
        payload = line.split(":", 1)[1].strip()
        if not payload:
            return None
        try:
            return ("data", json.loads(payload))
        except json.JSONDecodeError:
            fixed = re.sub(r'\\(?![\\"/bfnrtu])', r'\\\\', payload)
            try:
                return ("data", json.loads(fixed))
            except json.JSONDecodeError as e:
                dbg("SSE JSON decode failed after fix", (str(e), payload[:200]))
                return None
    return None


# ---------------------------------------------------------------------
# DeepSeek API client
# ---------------------------------------------------------------------

class DeepSeekAPI:
    BASE = "https://chat.deepseek.com"

    def __init__(self, token: str, session: aiohttp.ClientSession | None = None):
        self.token = token
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("DeepSeekAPI session is not open. Use 'async with'.")
        return self._session

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    # --- PoW ----------------------------------------------------------

    async def _solve_pow(self, target_path: str = "/api/v0/chat/completion") -> str:
        t0 = time.monotonic()
        async with self.session.post(
            f"{self.BASE}/api/v0/chat/create_pow_challenge",
            headers=self._auth_headers(),
            json={"target_path": target_path},
        ) as resp:
            data = await resp.json()
            challenge = data["data"]["biz_data"]["challenge"]
        dbg("pow challenge", challenge.get("difficulty"))

        solver = DeepSeekHash()
        answer = solver.calculate_hash(
            challenge["challenge"],
            challenge["salt"],
            challenge["difficulty"],
            challenge["expire_at"],
        )
        if answer is None:
            raise RuntimeError("PoW not solved")
        dbg("pow solved in", f"{(time.monotonic() - t0) * 1000:.1f} ms")

        result = {
            "algorithm": challenge["algorithm"],
            "challenge": challenge["challenge"],
            "salt": challenge["salt"],
            "answer": int(answer),
            "signature": challenge["signature"],
            "target_path": target_path,
        }
        return base64.b64encode(json.dumps(result).encode()).decode()

    # --- chat sessions ------------------------------------------------

    async def create_chat_session(self) -> str:
        async with self.session.post(
            f"{self.BASE}/api/v0/chat_session/create",
            headers=self._auth_headers(),
            json={},
        ) as resp:
            data = await resp.json()
            dbg("create_chat_session", json.dumps(data)[:300])
            try:
                return data["data"]["biz_data"]["chat_session"]["id"]
            except (KeyError, TypeError):
                biz = data.get("data", {}).get("biz_data", data)
                if isinstance(biz, dict):
                    if "chat_session" in biz and isinstance(biz["chat_session"], dict):
                        return biz["chat_session"]["id"]
                    if "id" in biz:
                        return biz["id"]
                raise ValueError(f"Could not find session ID. Response: {data}")

    async def fetch_chat_title(self, chat_id: str) -> str | None:
        try:
            async with self.session.get(
                f"{self.BASE}/api/v0/chat_session/fetch_page",
                headers=self._auth_headers(),
                params={"count": 50},
            ) as resp:
                data = await resp.json()
        except Exception as e:  # noqa: BLE001
            dbg("fetch_page failed", str(e))
            return None

        dbg("fetch_page", json.dumps(data)[:300])

        try:
            sessions = data.get("data", {}).get("biz_data", {}).get("sessions", [])
        except AttributeError:
            return None

        for item in sessions:
            if item.get("id") == chat_id:
                return item.get("title")
        return None

    # --- messages -----------------------------------------------------

    async def send_message(self, prompt: str, chat_id: str,
                           parent_message_id: int | None = None,
                           search: bool = False,
                           thinking: bool = False):
        t0 = time.monotonic()
        pow_response = await self._solve_pow()

        payload = {
            "chat_session_id": chat_id,
            "parent_message_id": parent_message_id,
            "model_type": None,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": thinking,
            "search_enabled": search,
            "action": None,
            "preempt": False,
        }
        dbg("send_message payload", {
            "chat": chat_id[:8],
            "parent": parent_message_id,
            "prompt_len": len(prompt),
            "search": search,
            "thinking": thinking,
        })

        content_parts: list[str] = []
        metadata = {}
        chunk_count = 0

        async with self.session.post(
            f"{self.BASE}/api/v0/chat/completion",
            headers={
                **self._auth_headers(),
                "x-ds-pow-response": pow_response,
                "Content-Type": "application/json",
            },
            json=payload,
        ) as resp:
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8", errors="ignore")
                parsed = parse_sse_line(line)
                if not parsed:
                    continue

                kind, value = parsed
                if kind == "event":
                    dbg("sse event", value)
                    continue

                obj = value
                if not isinstance(obj, dict):
                    continue

                if obj.get("o") == "APPEND" and obj.get("p") == "response/content":
                    chunk = obj.get("v", "")
                    if isinstance(chunk, str):
                        content_parts.append(chunk)
                        chunk_count += 1
                    continue

                if "v" in obj and isinstance(obj["v"], str):
                    chunk = obj["v"]
                    content_parts.append(chunk)
                    chunk_count += 1
                    continue

                if obj.get("o") == "SET":
                    dbg("sse set", (obj.get("p"), obj.get("v")))
                    continue

                if "v" in obj and isinstance(obj["v"], dict):
                    inner = obj["v"].get("response")
                    if inner and isinstance(inner.get("content"), str):
                        content_parts.append(inner["content"])
                    if inner and isinstance(inner.get("message_id"), int):
                        metadata["response_message_id"] = inner["message_id"]
                    continue

                for key in ("request_message_id", "response_message_id",
                            "model_type", "updated_at"):
                    if key in obj:
                        metadata[key] = obj[key]

        dbg("stream done", {
            "chunks": chunk_count,
            "chars": sum(len(c) for c in content_parts),
            "elapsed_ms": f"{(time.monotonic() - t0) * 1000:.0f}",
            "response_id": metadata.get("response_message_id"),
        })

        return "".join(content_parts), metadata.get("response_message_id")

# ---------------------------------------------------------------------
# Duck.AI API client
# ---------------------------------------------------------------------

class DuckAPI:
    BASE = "https://duck.ai/duckchat/v1"

    def __init__(self, session: aiohttp.ClientSession | None = None):
        self._session = session
        self._owns_session = session is None

    async def __aenter__(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None:
            raise RuntimeError("DuckAPI session is not open. Use 'async with'.")
        return self._session

    # --- headers ------------------------------------------------------

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            # No Authorization header needed for DuckDuckGo's privacy layer
        }

    # --- chat sessions ------------------------------------------------

    async def create_chat_session(self) -> str:
        """Create a new chat session (Duck.AI doesn't use sessions in the same way)."""
        payload = {
            "model": "mistral-small-2603",
            "messages": [],
            "metadata": {},
            "canUseTools": True
        }

        async with self.session.post(
            f"{self.BASE}/chat",
            headers=self._headers(),
            json=payload,
        ) as resp:
            data = await resp.json()
            dbg("create_chat_session", json.dumps(data)[:300])
            try:
                return data["conversationId"]  # Duck.AI uses conversationId instead of session ID
            except (KeyError, TypeError):
                raise ValueError(f"Could not find conversation ID. Response: {data}")

    async def fetch_chat_title(self, chat_id: str) -> str | None:
        """Fetch the title of a chat (Duck.AI doesn't expose titles in the same way)."""
        # Duck.AI doesn't provide a direct endpoint for chat titles
        # This is a placeholder - you might need to implement your own title tracking
        return None

    # --- messages -----------------------------------------------------

    async def send_message(self, prompt: str, chat_id: str,
                          parent_message_id: int | None = None):
        """
        Send a message to Duck.AI's API.

        Args:
            prompt: The message to send
            chat_id: The conversation ID (returned from create_chat_session)
            parent_message_id: Not used in Duck.AI's API (conversation is maintained via messages array)

        Returns:
            Tuple of (response_text, message_id)
        """
        t0 = time.monotonic()

        # Build the messages array with conversation history
        messages = [
            {
                "role": "user",
                "content": [{"type": "text", "text": prompt}]
            }
        ]

        payload = {
            "model": "mistral-small-2603",
            "messages": messages,
            "metadata": {},
            "canUseTools": True
        }

        content_parts: list[str] = []
        metadata = {}
        chunk_count = 0

        async with self.session.post(
            f"{self.BASE}/chat",
            headers=self._headers(),
            json=payload,
        ) as resp:
            async for raw_line in resp.content:
                line = raw_line.decode("utf-8", errors="ignore")
                parsed = parse_sse_line(line)
                if not parsed:
                    continue

                kind, value = parsed
                if kind == "event":
                    dbg("sse event", value)
                    continue

                obj = value
                if not isinstance(obj, dict):
                    continue

                # Handle different response formats from Duck.AI
                if obj.get("o") == "APPEND" and obj.get("p") == "response/content":
                    chunk = obj.get("v", "")
                    if isinstance(chunk, str):
                        content_parts.append(chunk)
                        chunk_count += 1
                    continue

                if set(obj.keys()) == {"v"}:
                    chunk = obj["v"]
                    if isinstance(chunk, str):
                        content_parts.append(chunk)
                        chunk_count += 1
                    continue

                if obj.get("o") == "SET":
                    dbg("sse set", (obj.get("p"), obj.get("v")))
                    continue

                if "v" in obj and isinstance(obj["v"], dict):
                    inner = obj["v"].get("response")
                    if inner and isinstance(inner.get("content"), str):
                        content_parts.append(inner["content"])
                    if inner and isinstance(inner.get("message_id"), int):
                        metadata["response_message_id"] = inner["message_id"]
                    continue

                for key in ("request_message_id", "response_message_id",
                          "model_type", "updated_at"):
                    if key in obj:
                        metadata[key] = obj[key]

        dbg("stream done", {
            "chunks": chunk_count,
            "chars": sum(len(c) for c in content_parts),
            "elapsed_ms": f"{(time.monotonic() - t0) * 1000:.0f}",
            "response_id": metadata.get("response_message_id"),
        })

        return "".join(content_parts), metadata.get("response_message_id")