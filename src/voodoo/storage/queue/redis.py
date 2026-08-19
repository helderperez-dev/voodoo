"""Redis queue provider (Sprint 13).

``RedisQueue`` implements the ``VoodooQueue`` capability over a Redis
server using **sorted sets + per-task hashes + atomic Lua scripts** (not
streams/consumer groups — streams cannot honor the priority ordering,
delayed delivery, idempotency dedup, or per-status stats/list that the
``QueueContractTests`` suite requires).

Data model (all keys under the ``voodoo:queue:`` namespace):

- ``seq`` — INCR counter producing task ids.
- ``task:{id}`` — hash holding all 16 ``TaskRecord`` fields (payload as JSON,
  datetimes as epoch seconds).
- ``ready`` — ZSET of claimable tasks, score = ``-priority``, member =
  zero-padded id (so priority DESC, then id ASC).
- ``type:{type}`` — per-type ZSET of claimable tasks (for ``claim(types=...)``).
- ``delayed`` — ZSET of not-yet-available tasks, score = ``available_at``.
- ``status:{pending|running|retrying|completed|failed}`` — SETs for stats/list.
- ``all`` — ZSET of every task, score = ``created_at`` (for ``list()``).
- ``idem:{key}`` — idempotency key → task id (SET NX), DEL on terminal.

Every state transition is an atomic Lua script, so concurrent workers can
never claim the same task (mirroring SQLite/Postgres ``FOR UPDATE SKIP
LOCKED``). Durability comes from Redis AOF/RDB persistence (documented in
``docs/deployment.md``); capability declaration stays honest
(``ordering="best_effort"``).

redis-py is an optional dependency — nothing on the default path imports it.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from voodoo.core.errors import ConfigurationError
from voodoo.storage.queue.interfaces import (
    QueueCapabilities,
    QueueStats,
    TaskRecord,
    TaskStatus,
)

try:
    import redis as _redis
except ImportError:  # pragma: no cover - exercised when redis is absent
    _redis = None

# ---------------------------------------------------------------------------
# Lua scripts (atomic state transitions)
#
# ZSET members are zero-padded ids (string.format('%012d', id)) so that
# lexicographic member order == numeric id order for equal scores (the
# contract's priority DESC, id ASC tie-break). Status SETs and task hashes
# use the raw numeric id.
# ---------------------------------------------------------------------------

_ENQUEUE_SCRIPT = """
local task_type = ARGV[1]
local payload = ARGV[2]
local priority = ARGV[3]
local available_at = ARGV[4]
local max_attempts = ARGV[5]
local idem_key = ARGV[6]
local trace_id = ARGV[7]
local created_at = ARGV[8]
local delay = tonumber(ARGV[9])
local hash_prefix = ARGV[10]
local ready_key = ARGV[11]
local delayed_key = ARGV[12]
local all_key = ARGV[13]
local pending_set = ARGV[14]
local type_prefix = ARGV[15]
local idem_prefix = ARGV[16]
local seq_key = ARGV[17]

local function pad(id) return string.format('%012d', tonumber(id)) end

if idem_key ~= '' then
  local existing = redis.call('GET', idem_prefix .. idem_key)
  if existing then
    local st = redis.call('HGET', hash_prefix .. existing, 'status')
    if st and st ~= 'completed' and st ~= 'failed' then
      return redis.call('HGETALL', hash_prefix .. existing)
    else
      redis.call('DEL', idem_prefix .. idem_key)
    end
  end
end

local id = redis.call('INCR', seq_key)
local padded = pad(id)
local hash = hash_prefix .. id
redis.call('HSET', hash,
  'id', id,
  'type', task_type,
  'payload', payload,
  'status', 'pending',
  'priority', priority,
  'available_at', available_at,
  'attempts', 0,
  'max_attempts', max_attempts,
  'locked_by', '',
  'locked_at', '',
  'lease_until', '',
  'idempotency_key', idem_key,
  'trace_id', trace_id,
  'created_at', created_at,
  'completed_at', '',
  'last_error', ''
)
redis.call('ZADD', all_key, created_at, padded)
redis.call('SADD', pending_set, id)
if idem_key ~= '' then
  redis.call('SET', idem_prefix .. idem_key, id)
end
if delay > 0 then
  redis.call('ZADD', delayed_key, available_at, padded)
else
  local score = -tonumber(priority)
  redis.call('ZADD', ready_key, score, padded)
  redis.call('ZADD', type_prefix .. task_type, score, padded)
end
return redis.call('HGETALL', hash)
"""

_CLAIM_SCRIPT = """
local now = tonumber(ARGV[1])
local worker = ARGV[2]
local lease_until = ARGV[3]
local locked_at = ARGV[4]
local types = ARGV[5]
local hash_prefix = ARGV[6]
local ready_key = ARGV[7]
local delayed_key = ARGV[8]
local type_prefix = ARGV[9]
local status_prefix = ARGV[10]

local function pad(id) return string.format('%012d', tonumber(id)) end

-- 1. Promote due delayed tasks to ready.
local due = redis.call('ZRANGEBYSCORE', delayed_key, '-inf', now)
for _, padded in ipairs(due) do
  local id = tonumber(padded)
  local hash = hash_prefix .. id
  local t = redis.call('HGET', hash, 'type')
  local prio = redis.call('HGET', hash, 'priority')
  local score = -tonumber(prio)
  redis.call('ZADD', ready_key, score, padded)
  if t then redis.call('ZADD', type_prefix .. t, score, padded) end
  redis.call('HSET', hash, 'status', 'pending')
  redis.call('SREM', status_prefix .. 'retrying', id)
  redis.call('SADD', status_prefix .. 'pending', id)
  redis.call('ZREM', delayed_key, padded)
end

-- 2. Collect candidate ids (padded members).
local candidates = {}
if types == '' then
  local best = redis.call('ZRANGEBYSCORE', ready_key, '-inf', '+inf', 'LIMIT', 0, 1)
  if #best > 0 then candidates = best end
else
  for t in string.gmatch(types, '[^,]+') do
    local best = redis.call('ZRANGEBYSCORE', type_prefix .. t, '-inf', '+inf', 'LIMIT', 0, 1)
    if #best > 0 then table.insert(candidates, best[1]) end
  end
end

if #candidates == 0 then return false end

-- 3. Pick the best (priority DESC, then id ASC). Lower ZSET score wins
--    (score = -priority); equal scores break on the padded member, whose
--    lexicographic order equals numeric id order.
local best_id = candidates[1]
local best_score = redis.call('ZSCORE', ready_key, best_id)
for i = 2, #candidates do
  local id = candidates[i]
  local score = redis.call('ZSCORE', ready_key, id)
  if score < best_score or (score == best_score and id < best_id) then
    best_id = id
    best_score = score
  end
end

-- 4. Claim it.
local id = tonumber(best_id)
local hash = hash_prefix .. id
local t = redis.call('HGET', hash, 'type')
local attempts = tonumber(redis.call('HGET', hash, 'attempts') or '0') + 1
redis.call('ZREM', ready_key, best_id)
if t then redis.call('ZREM', type_prefix .. t, best_id) end
redis.call('HSET', hash, 'status', 'running', 'attempts', attempts,
  'locked_by', worker, 'locked_at', locked_at, 'lease_until', lease_until)
redis.call('SREM', status_prefix .. 'pending', id)
redis.call('SREM', status_prefix .. 'retrying', id)
redis.call('SADD', status_prefix .. 'running', id)
return redis.call('HGETALL', hash)
"""

_HEARTBEAT_SCRIPT = """
local hash = ARGV[1] .. ARGV[2]
local worker = ARGV[3]
local locked_at = ARGV[4]
local lease_until = ARGV[5]
if redis.call('HGET', hash, 'locked_by') == worker
   and redis.call('HGET', hash, 'status') == 'running' then
  redis.call('HSET', hash, 'locked_at', locked_at, 'lease_until', lease_until)
  return 1
end
return 0
"""

_COMPLETE_SCRIPT = """
local hash = ARGV[1] .. ARGV[2]
local worker = ARGV[3]
local completed_at = ARGV[4]
local status_prefix = ARGV[5]
local idem_prefix = ARGV[6]
if redis.call('HGET', hash, 'locked_by') == worker
   and redis.call('HGET', hash, 'status') == 'running' then
  redis.call('HSET', hash, 'status', 'completed', 'completed_at', completed_at,
    'locked_by', '', 'locked_at', '', 'lease_until', '')
  redis.call('SREM', status_prefix .. 'running', ARGV[2])
  redis.call('SADD', status_prefix .. 'completed', ARGV[2])
  local idem = redis.call('HGET', hash, 'idempotency_key')
  if idem and idem ~= '' then redis.call('DEL', idem_prefix .. idem) end
  return 1
end
return 0
"""

_FAIL_SCRIPT = """
local hash = ARGV[1] .. ARGV[2]
local worker = ARGV[3]
local error = ARGV[4]
local now = tonumber(ARGV[5])
local backoff_base = tonumber(ARGV[6])
local status_prefix = ARGV[7]
local delayed_key = ARGV[8]
local idem_prefix = ARGV[9]

if redis.call('HGET', hash, 'locked_by') ~= worker
   or redis.call('HGET', hash, 'status') ~= 'running' then
  return false
end
local attempts = tonumber(redis.call('HGET', hash, 'attempts'))
local max_attempts = tonumber(redis.call('HGET', hash, 'max_attempts'))
redis.call('SREM', status_prefix .. 'running', ARGV[2])
if attempts < max_attempts then
  local delay = backoff_base * (2 ^ math.max(0, attempts - 1))
  local available_at = now + delay
  redis.call('HSET', hash, 'status', 'retrying', 'available_at', available_at,
    'completed_at', '', 'locked_by', '', 'locked_at', '', 'lease_until', '',
    'last_error', error)
  redis.call('SADD', status_prefix .. 'retrying', ARGV[2])
  redis.call('ZADD', delayed_key, available_at, ARGV[2])
else
  redis.call('HSET', hash, 'status', 'failed', 'available_at', now,
    'completed_at', now, 'locked_by', '', 'locked_at', '', 'lease_until', '',
    'last_error', error)
  redis.call('SADD', status_prefix .. 'failed', ARGV[2])
  local idem = redis.call('HGET', hash, 'idempotency_key')
  if idem and idem ~= '' then redis.call('DEL', idem_prefix .. idem) end
end
return redis.call('HGETALL', hash)
"""

_RELEASE_SCRIPT = """
local hash = ARGV[1] .. ARGV[2]
local worker = ARGV[3]
local status_prefix = ARGV[4]
local ready_key = ARGV[5]
local type_prefix = ARGV[6]
local function pad(id) return string.format('%012d', tonumber(id)) end
if redis.call('HGET', hash, 'locked_by') == worker
   and redis.call('HGET', hash, 'status') == 'running' then
  local t = redis.call('HGET', hash, 'type')
  local prio = redis.call('HGET', hash, 'priority')
  local score = -tonumber(prio)
  local padded = pad(ARGV[2])
  redis.call('HSET', hash, 'status', 'pending', 'locked_by', '',
    'locked_at', '', 'lease_until', '')
  redis.call('SREM', status_prefix .. 'running', ARGV[2])
  redis.call('SADD', status_prefix .. 'pending', ARGV[2])
  redis.call('ZADD', ready_key, score, padded)
  if t then redis.call('ZADD', type_prefix .. t, score, padded) end
  return 1
end
return 0
"""

_RELEASE_EXPIRED_SCRIPT = """
local now = tonumber(ARGV[1])
local status_prefix = ARGV[2]
local ready_key = ARGV[3]
local type_prefix = ARGV[4]
local hash_prefix = ARGV[5]
local idem_prefix = ARGV[6]

local function pad(id) return string.format('%012d', tonumber(id)) end

local running_ids = redis.call('SMEMBERS', status_prefix .. 'running')
local reclaimed = 0
for _, id in ipairs(running_ids) do
  local hash = hash_prefix .. id
  local lease_until = tonumber(redis.call('HGET', hash, 'lease_until') or '0')
  if lease_until > 0 and lease_until < now then
    local attempts = tonumber(redis.call('HGET', hash, 'attempts'))
    local max_attempts = tonumber(redis.call('HGET', hash, 'max_attempts'))
    local t = redis.call('HGET', hash, 'type')
    local prio = redis.call('HGET', hash, 'priority')
    local score = -tonumber(prio)
    local last_error = redis.call('HGET', hash, 'last_error')
    if last_error == '' then last_error = 'lease expired' end
    redis.call('SREM', status_prefix .. 'running', id)
    if attempts >= max_attempts then
      redis.call('HSET', hash, 'status', 'failed', 'completed_at', now,
        'last_error', last_error, 'locked_by', '', 'locked_at', '',
        'lease_until', '')
      redis.call('SADD', status_prefix .. 'failed', id)
      local idem = redis.call('HGET', hash, 'idempotency_key')
      if idem and idem ~= '' then redis.call('DEL', idem_prefix .. idem) end
    else
      local padded = pad(id)
      redis.call('HSET', hash, 'status', 'pending', 'available_at', now,
        'last_error', last_error, 'locked_by', '', 'locked_at', '',
        'lease_until', '')
      redis.call('SADD', status_prefix .. 'pending', id)
      redis.call('ZADD', ready_key, score, padded)
      if t then redis.call('ZADD', type_prefix .. t, score, padded) end
    end
    reclaimed = reclaimed + 1
  end
end
return reclaimed
"""

_RETRY_SCRIPT = """
local hash = ARGV[1] .. ARGV[2]
local now = tonumber(ARGV[3])
local status_prefix = ARGV[4]
local ready_key = ARGV[5]
local type_prefix = ARGV[6]
local function pad(id) return string.format('%012d', tonumber(id)) end
if redis.call('HGET', hash, 'status') == 'failed' then
  local t = redis.call('HGET', hash, 'type')
  local prio = redis.call('HGET', hash, 'priority')
  local score = -tonumber(prio)
  local padded = pad(ARGV[2])
  redis.call('HSET', hash, 'status', 'pending', 'attempts', 0,
    'available_at', now, 'completed_at', '', 'locked_by', '',
    'locked_at', '', 'lease_until', '', 'last_error', '')
  redis.call('SREM', status_prefix .. 'failed', ARGV[2])
  redis.call('SADD', status_prefix .. 'pending', ARGV[2])
  redis.call('ZADD', ready_key, score, padded)
  if t then redis.call('ZADD', type_prefix .. t, score, padded) end
  return redis.call('HGETALL', hash)
end
return false
"""


def _now() -> datetime:
    return datetime.now(UTC)


def _epoch(dt: datetime) -> float:
    return dt.timestamp()


def _from_epoch(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return datetime.fromtimestamp(float(ts), tz=UTC)


def _hash_to_dict(flat: list[Any]) -> dict[str, str]:
    return {str(flat[i]): str(flat[i + 1]) for i in range(0, len(flat), 2)}


class RedisQueue:
    """Durable queue on a Redis server (ZSETs + hashes + Lua)."""

    provider = "redis"

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        if _redis is None:
            raise ConfigurationError(
                "The redis queue provider requires the [redis] extra: "
                "pip install 'voodoo-framework[redis]' (redis)."
            )
        self.url = url
        self._client = _redis.asyncio.Redis.from_url(url, decode_responses=True)
        self._ns = "voodoo:queue:"

    # -- lifecycle -----------------------------------------------------------

    async def setup(self) -> None:
        # Idempotent: verify connectivity; no schema to create.
        await self._client.ping()

    async def close(self) -> None:
        await self._client.aclose()

    # -- enqueue -------------------------------------------------------------

    async def enqueue(
        self,
        task_type: str,
        payload: Any,
        *,
        priority: int = 0,
        delay: float = 0.0,
        max_attempts: int = 1,
        idempotency_key: str | None = None,
        trace_id: str | None = None,
    ) -> TaskRecord:
        now = _now()
        available_at = now + timedelta(seconds=delay) if delay > 0 else now
        flat = await self._client.eval(
            _ENQUEUE_SCRIPT,
            0,
            task_type,
            json.dumps(payload) if payload is not None else "",
            str(priority),
            str(_epoch(available_at)),
            str(max(1, int(max_attempts))),
            idempotency_key or "",
            trace_id or "",
            str(_epoch(now)),
            "1" if delay > 0 else "0",
            f"{self._ns}task:",
            f"{self._ns}ready",
            f"{self._ns}delayed",
            f"{self._ns}all",
            f"{self._ns}status:pending",
            f"{self._ns}type:",
            f"{self._ns}idem:",
            f"{self._ns}seq",
        )
        return self._record_from_hash(_hash_to_dict(flat))

    # -- claim / lease -------------------------------------------------------

    async def claim(
        self,
        worker: str,
        *,
        types: Sequence[str] | None = None,
        lease_seconds: float = 60.0,
    ) -> TaskRecord | None:
        now = _now()
        lease_until = now + timedelta(seconds=lease_seconds)
        flat = await self._client.eval(
            _CLAIM_SCRIPT,
            0,
            str(_epoch(now)),
            worker,
            str(_epoch(lease_until)),
            str(_epoch(now)),
            ",".join(types) if types else "",
            f"{self._ns}task:",
            f"{self._ns}ready",
            f"{self._ns}delayed",
            f"{self._ns}type:",
            f"{self._ns}status:",
        )
        if not flat:
            return None
        return self._record_from_hash(_hash_to_dict(flat))

    async def heartbeat(
        self, task_id: int, worker: str, *, lease_seconds: float = 60.0
    ) -> bool:
        now = _now()
        result = await self._client.eval(
            _HEARTBEAT_SCRIPT,
            0,
            f"{self._ns}task:",
            str(task_id),
            worker,
            str(_epoch(now)),
            str(_epoch(now + timedelta(seconds=lease_seconds))),
        )
        return bool(result)

    async def complete(self, task_id: int, worker: str) -> bool:
        result = await self._client.eval(
            _COMPLETE_SCRIPT,
            0,
            f"{self._ns}task:",
            str(task_id),
            worker,
            str(_epoch(_now())),
            f"{self._ns}status:",
            f"{self._ns}idem:",
        )
        return bool(result)

    async def fail(
        self,
        task_id: int,
        worker: str,
        error: str,
        *,
        backoff_base: float = 1.0,
    ) -> TaskRecord | None:
        flat = await self._client.eval(
            _FAIL_SCRIPT,
            0,
            f"{self._ns}task:",
            str(task_id),
            worker,
            error,
            str(_epoch(_now())),
            str(backoff_base),
            f"{self._ns}status:",
            f"{self._ns}delayed",
            f"{self._ns}idem:",
        )
        if not flat:
            return None
        return self._record_from_hash(_hash_to_dict(flat))

    async def release(self, task_id: int, worker: str) -> bool:
        result = await self._client.eval(
            _RELEASE_SCRIPT,
            0,
            f"{self._ns}task:",
            str(task_id),
            worker,
            f"{self._ns}status:",
            f"{self._ns}ready",
            f"{self._ns}type:",
        )
        return bool(result)

    async def release_expired(self) -> int:
        result = await self._client.eval(
            _RELEASE_EXPIRED_SCRIPT,
            0,
            str(_epoch(_now())),
            f"{self._ns}status:",
            f"{self._ns}ready",
            f"{self._ns}type:",
            f"{self._ns}task:",
            f"{self._ns}idem:",
        )
        return int(result or 0)

    async def retry(self, task_id: int) -> TaskRecord | None:
        flat = await self._client.eval(
            _RETRY_SCRIPT,
            0,
            f"{self._ns}task:",
            str(task_id),
            str(_epoch(_now())),
            f"{self._ns}status:",
            f"{self._ns}ready",
            f"{self._ns}type:",
        )
        if not flat:
            return None
        return self._record_from_hash(_hash_to_dict(flat))

    # -- inspection ----------------------------------------------------------

    async def list(
        self,
        *,
        status: TaskStatus | str | None = None,
        task_type: str | None = None,
        limit: int = 50,
    ) -> list[TaskRecord]:
        if status is not None:
            status_val = TaskStatus(status).value
            ids = await self._client.smembers(f"{self._ns}status:{status_val}")
        else:
            ids = await self._client.zrevrange(f"{self._ns}all", 0, -1)
        records: list[TaskRecord] = []
        for raw_id in ids:
            rec = await self._get_record(int(raw_id))
            if rec is None:
                continue
            if task_type is not None and rec.type != task_type:
                continue
            records.append(rec)
        records.sort(
            key=lambda r: r.created_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )
        return records[:limit]

    async def stats(self) -> QueueStats:
        pending = await self._client.scard(f"{self._ns}status:pending")
        running = await self._client.scard(f"{self._ns}status:running")
        retrying = await self._client.scard(f"{self._ns}status:retrying")
        completed = await self._client.scard(f"{self._ns}status:completed")
        failed = await self._client.scard(f"{self._ns}status:failed")
        return QueueStats(
            total=pending + running + retrying + completed + failed,
            pending=pending,
            running=running,
            retrying=retrying,
            completed=completed,
            failed=failed,
        )

    def capabilities(self) -> QueueCapabilities:
        return QueueCapabilities(
            provider=self.provider,
            durable=True,
            delivery="at_least_once",
            ordering="best_effort",
            visibility_timeout=True,
            delayed_delivery=True,
            priority=True,
            transactions=True,
        )

    # -- helpers -------------------------------------------------------------

    async def _get_record(self, task_id: int) -> TaskRecord | None:
        flat = await self._client.hgetall(f"{self._ns}task:{task_id}")
        if not flat:
            return None
        return self._record_from_hash(flat)

    def _record_from_hash(self, h: dict[str, str]) -> TaskRecord:
        return TaskRecord(
            id=int(h["id"]),
            type=h["type"],
            payload=json.loads(h["payload"]) if h.get("payload") else None,
            status=TaskStatus(h["status"]),
            priority=int(h["priority"]),
            available_at=_from_epoch(h.get("available_at")),
            attempts=int(h["attempts"]),
            max_attempts=int(h["max_attempts"]),
            locked_by=h.get("locked_by") or None,
            locked_at=_from_epoch(h.get("locked_at")),
            lease_until=_from_epoch(h.get("lease_until")),
            idempotency_key=h.get("idempotency_key") or None,
            trace_id=h.get("trace_id") or None,
            created_at=_from_epoch(h.get("created_at")),
            completed_at=_from_epoch(h.get("completed_at")),
            last_error=h.get("last_error") or None,
        )


if TYPE_CHECKING:
    from voodoo.storage.queue.interfaces import VoodooQueue

    _protocol_check: VoodooQueue = RedisQueue()
