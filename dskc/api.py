import base64
import json
import aiohttp
from pow_solver import DeepSeekHash

DEBUG = "--debug" in __import__("sys").argv


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
            return None
    return None


async def solve_pow(session, token, target_path="/api/v0/chat/completion"):
    async with session.post(
        "https://chat.deepseek.com/api/v0/chat/create_pow_challenge",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_path": target_path},
    ) as resp:
        data = await resp.json()
        challenge = data["data"]["biz_data"]["challenge"]

    solver = DeepSeekHash()
    answer = solver.calculate_hash(
        challenge["challenge"],
        challenge["salt"],
        challenge["difficulty"],
        challenge["expire_at"],
    )
    if answer is None:
        raise RuntimeError("PoW not solved")

    result = {
        "algorithm": challenge["algorithm"],
        "challenge": challenge["challenge"],
        "salt": challenge["salt"],
        "answer": int(answer),
        "signature": challenge["signature"],
        "target_path": target_path,
    }
    return base64.b64encode(json.dumps(result).encode()).decode()


async def create_chat_session(session, token) -> str:
    async with session.post(
        "https://chat.deepseek.com/api/v0/chat_session/create",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    ) as resp:
        data = await resp.json()
        if DEBUG:
            print(f"[DEBUG] create_chat_session raw: {json.dumps(data)[:500]}")
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


async def fetch_chat_title(session, token, chat_id: str) -> str | None:
    try:
        async with session.get(
            "https://chat.deepseek.com/api/v0/chat_session/fetch_page",
            headers={"Authorization": f"Bearer {token}"},
            params={"count": 50},
        ) as resp:
            data = await resp.json()
    except Exception:
        return None

    if DEBUG:
        print(f"[DEBUG] fetch_page raw: {json.dumps(data)[:500]}")

    try:
        sessions = data.get("data", {}).get("biz_data", {}).get("sessions", [])
    except AttributeError:
        return None

    for item in sessions:
        if item.get("id") == chat_id:
            return item.get("title")
    return None


async def send_message(session, token, prompt: str, chat_id: str,
                       parent_message_id: int | None = None):
    pow_response = await solve_pow(session, token)

    payload = {
        "chat_session_id": chat_id,
        "parent_message_id": parent_message_id,
        "prompt": prompt,
        "ref_file_ids": [],
        "thinking_enabled": False,
        "search_enabled": False,
    }

    content_parts: list[str] = []
    metadata = {}

    async with session.post(
        "https://chat.deepseek.com/api/v0/chat/completion",
        headers={
            "Authorization": f"Bearer {token}",
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
            if DEBUG:
                print(f"[DEBUG] {kind}: {json.dumps(value)[:200]}")

            if kind == "event":
                continue

            obj = value
            if not isinstance(obj, dict):
                continue

            if obj.get("o") == "APPEND" and obj.get("p") == "response/content":
                chunk = obj.get("v", "")
                if isinstance(chunk, str):
                    content_parts.append(chunk)
                continue

            if set(obj.keys()) == {"v"}:
                chunk = obj["v"]
                if isinstance(chunk, str):
                    content_parts.append(chunk)
                continue

            if obj.get("o") == "SET":
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

    return "".join(content_parts), metadata.get("response_message_id")