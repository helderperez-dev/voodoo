"""Provider registry mapping configuration names to adapter factories (Spec §31, §28).

All adapters implemented across Sprints 1–7 are registered here. Future
adapters (Postgres, S3/R2 hardening, Redis, etc.) register their factories
alongside these defaults.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from voodoo.config import (
    CacheConfig,
    DatabaseConfig,
    EventsConfig,
    ObjectsConfig,
    QueueConfig,
    get_config,
)
from voodoo.core.errors import ConfigurationError

# Type alias for provider factories
DatabaseFactory = Callable[[DatabaseConfig], Any]
QueueFactory = Callable[[QueueConfig], Any]
EventsFactory = Callable[[EventsConfig], Any]
ObjectsFactory = Callable[[ObjectsConfig], Any]
CacheFactory = Callable[[CacheConfig], Any]


class ProviderRegistry:
    """Registry mapping category + provider name to factory functions."""

    def __init__(self) -> None:
        self._database_providers: dict[str, DatabaseFactory] = {}
        self._queue_providers: dict[str, QueueFactory] = {}
        self._events_providers: dict[str, EventsFactory] = {}
        self._objects_providers: dict[str, ObjectsFactory] = {}
        self._cache_providers: dict[str, CacheFactory] = {}

        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in adapters from Sprints 1–7."""
        # 1. Database providers
        self.register_database("sqlite", self._create_sqlite_database)
        self.register_database("postgres", self._create_postgres_database)

        # 2. Queue providers
        self.register_queue("sqlite", self._create_sqlite_queue)
        self.register_queue("memory", self._create_memory_queue)
        self.register_queue("postgres", self._create_postgres_queue)
        self.register_queue("redis", self._create_redis_queue)

        # 3. Events providers
        self.register_events("sqlite", self._create_sqlite_events)
        self.register_events("local", self._create_local_events)
        self.register_events("postgres", self._create_postgres_events)

        # 4. Objects providers
        self.register_objects("local", self._create_local_objects)
        self.register_objects("s3", self._create_s3_objects)

        # 5. Cache providers
        self.register_cache("memory", self._create_memory_cache)
        self.register_cache("redis", self._create_redis_cache)

    # --- Registration methods ---

    def register_database(self, name: str, factory: DatabaseFactory) -> None:
        self._database_providers[name.lower()] = factory

    def register_queue(self, name: str, factory: QueueFactory) -> None:
        self._queue_providers[name.lower()] = factory

    def register_events(self, name: str, factory: EventsFactory) -> None:
        self._events_providers[name.lower()] = factory

    def register_objects(self, name: str, factory: ObjectsFactory) -> None:
        self._objects_providers[name.lower()] = factory

    def register_cache(self, name: str, factory: CacheFactory) -> None:
        self._cache_providers[name.lower()] = factory

    # --- Factory invocation methods ---

    def get_database(
        self, cfg: DatabaseConfig | None = None, migrations: Sequence[Any] = ()
    ) -> Any:
        cfg = cfg or get_config().database
        name = cfg.provider.lower()
        if name not in self._database_providers:
            available = ", ".join(sorted(self._database_providers.keys()))
            raise ConfigurationError(
                f"Unknown database provider '{name}'. Available providers: {available}. "
                "Check your voodoo.yaml or VOODOO_DATABASE_PROVIDER setting."
            )
        return self._database_providers[name](cfg, migrations=migrations)

    def get_queue(self, cfg: QueueConfig | None = None, db: Any = None) -> Any:
        cfg = cfg or get_config().queue
        name = cfg.provider.lower()
        if name not in self._queue_providers:
            available = ", ".join(sorted(self._queue_providers.keys()))
            raise ConfigurationError(
                f"Unknown queue provider '{name}'. Available providers: {available}. "
                "Check your voodoo.yaml or VOODOO_QUEUE_PROVIDER setting."
            )
        # Database-backed queues (SQLite/Postgres) require a database
        # instance; allow passing one or create the default.
        if name in ("sqlite", "postgres"):
            return self._queue_providers[name](cfg, db=db)
        return self._queue_providers[name](cfg)

    def get_events(self, cfg: EventsConfig | None = None) -> Any:
        cfg = cfg or get_config().events
        name = cfg.provider.lower()
        if name not in self._events_providers:
            available = ", ".join(sorted(self._events_providers.keys()))
            raise ConfigurationError(
                f"Unknown events provider '{name}'. Available providers: {available}. "
                "Check your voodoo.yaml or VOODOO_EVENTS_PROVIDER setting."
            )
        return self._events_providers[name](cfg)

    def get_objects(self, cfg: ObjectsConfig | None = None) -> Any:
        cfg = cfg or get_config().objects
        name = cfg.provider.lower()
        if name not in self._objects_providers:
            available = ", ".join(sorted(self._objects_providers.keys()))
            raise ConfigurationError(
                f"Unknown objects provider '{name}'. Available providers: {available}. "
                "Check your voodoo.yaml or VOODOO_OBJECTS_PROVIDER setting."
            )
        return self._objects_providers[name](cfg)

    def get_cache(self, cfg: CacheConfig | None = None) -> Any:
        cfg = cfg or get_config().cache
        name = cfg.provider.lower()
        if name not in self._cache_providers:
            available = ", ".join(sorted(self._cache_providers.keys()))
            raise ConfigurationError(
                f"Unknown cache provider '{name}'. Available providers: {available}. "
                "Check your voodoo.yaml or VOODOO_CACHE_PROVIDER setting."
            )
        return self._cache_providers[name](cfg)

    # --- Built-in provider factory implementations ---

    def _create_sqlite_database(
        self, cfg: DatabaseConfig, migrations: Sequence[Any] = ()
    ) -> Any:
        from voodoo.storage.database.sqlite import SQLiteDatabase

        path = cfg.path or cfg.url or ".voodoo/state/data.db"
        if path.startswith("sqlite:///"):
            path = path[len("sqlite:///") :] or ":memory:"
        elif path == "sqlite://":
            path = ":memory:"
        return SQLiteDatabase(path, migrations=migrations)

    def _create_postgres_database(
        self, cfg: DatabaseConfig, migrations: Sequence[Any] = ()
    ) -> Any:
        """Build a :class:`~voodoo.storage.database.postgres.PostgresDatabase`.

        URL resolution order (Sprint 10):
        1. ``cfg.url`` from ``voodoo.yaml`` (``database.url``);
        2. ``VOODOO_DATABASE_URL`` environment variable;
        3. parts in ``cfg.extra`` (``host``/``port``/``dbname``/``user``/
           ``password``) — assembled into a ``postgresql://`` URL.

        Raises a clear ``ConfigurationError`` when none is available so the
        user is told exactly what to set, rather than failing inside psycopg.
        """
        import os

        from voodoo.storage.database.postgres import PostgresDatabase

        url = cfg.url
        if not url:
            url = os.getenv("VOODOO_DATABASE_URL", "")
        if not url:
            host = cfg.extra.get("host") or "localhost"
            port = cfg.extra.get("port") or "5432"
            dbname = cfg.extra.get("dbname") or cfg.extra.get("database") or "voodoo"
            user = cfg.extra.get("user") or cfg.extra.get("username") or "postgres"
            password = cfg.extra.get("password") or ""
            creds = f"{user}:{password}@" if password else f"{user}@"
            url = f"postgresql://{creds}{host}:{port}/{dbname}"
        return PostgresDatabase(url, migrations=migrations)

    def _create_sqlite_queue(self, cfg: QueueConfig, db: Any = None) -> Any:
        from voodoo.storage.queue.sqlite import SQLiteQueue

        if db is None:
            db = self.get_database()
        return SQLiteQueue(db)

    def _create_postgres_queue(self, cfg: QueueConfig, db: Any = None) -> Any:
        from voodoo.storage.queue.postgres import PostgresQueue

        if db is None:
            db = self.get_database()
        # The caller (app/worker) may hand us a Postgres database already
        # connected; assert it so a mixed provider (memory queue over
        # postgres db) still fails loudly at startup.
        if not hasattr(db, "provider") or db.provider != "postgres":
            raise ConfigurationError(
                "The 'postgres' queue provider requires a postgres database; "
                "set database.provider: postgres (or pass a PostgresDatabase)."
            )
        return PostgresQueue(db)

    def _create_memory_queue(self, cfg: QueueConfig) -> Any:
        from voodoo.storage.queue.memory import MemoryQueue

        return MemoryQueue()

    def _create_redis_queue(self, cfg: QueueConfig) -> Any:
        """Build a :class:`~voodoo.storage.queue.redis.RedisQueue`.

        URL resolution order (Sprint 13):
        1. ``cfg.url`` from ``voodoo.yaml`` (``queue.url``);
        2. ``VOODOO_QUEUE_URL`` environment variable;
        3. ``VOODOO_REDIS_URL`` environment variable;
        4. parts in ``cfg.extra`` (``host``/``port``/``db``) — assembled into
           a ``redis://`` URL;
        5. ``redis://localhost:6379/0``.

        Raises a clear ``ConfigurationError`` when the ``[redis]`` extra is
        not installed (lazy import, mirrors the postgres factory).
        """
        import os

        from voodoo.storage.queue.redis import RedisQueue

        url = (
            cfg.url
            or os.getenv("VOODOO_QUEUE_URL")
            or os.getenv("VOODOO_REDIS_URL")
            or ""
        )
        if not url:
            host = cfg.extra.get("host") or "localhost"
            port = cfg.extra.get("port") or "6379"
            db = cfg.extra.get("db") or "0"
            url = f"redis://{host}:{port}/{db}"
        return RedisQueue(url)

    def _create_sqlite_events(self, cfg: EventsConfig) -> Any:
        from voodoo.storage.events.sqlite import SQLiteEventBus

        path = cfg.path or cfg.url or ".voodoo/state/data.db"
        if path.startswith("sqlite:///"):
            path = path[len("sqlite:///") :] or ":memory:"
        elif path == "sqlite://":
            path = ":memory:"
        return SQLiteEventBus(path)

    def _create_local_events(self, cfg: EventsConfig) -> Any:
        from voodoo.storage.events.local import LocalEventBus

        return LocalEventBus()

    def _create_postgres_events(self, cfg: EventsConfig) -> Any:
        import os

        from voodoo.storage.events.postgres import PostgresEventStore

        url = (
            cfg.url
            or os.getenv("VOODOO_EVENTS_URL")
            or os.getenv("VOODOO_DATABASE_URL", "")
        )
        if not url:
            raise ConfigurationError(
                "The 'postgres' events provider requires a URL: set events.url "
                "in voodoo.yaml, or export VOODOO_EVENTS_URL / VOODOO_DATABASE_URL."
            )
        return PostgresEventStore(url)

    def _create_local_objects(self, cfg: ObjectsConfig) -> Any:
        from voodoo.storage.objects.local import LocalObjectStore

        base_dir = cfg.base_dir or ".voodoo/objects"
        return LocalObjectStore(base_dir)

    def _create_s3_objects(self, cfg: ObjectsConfig) -> Any:
        import os

        from voodoo.storage.objects.s3 import S3ObjectStore

        bucket = (
            cfg.bucket
            or os.getenv("VOODOO_BUCKET")
            or os.getenv("AWS_BUCKET")
            or os.getenv("VOODOO_S3_BUCKET")
            or "voodoo-objects"
        )
        endpoint = (
            cfg.endpoint
            or os.getenv("VOODOO_OBJECTS_ENDPOINT")
            or os.getenv("AWS_ENDPOINT_URL")
            or os.getenv("VOODOO_S3_ENDPOINT")
        )
        access_key = (
            cfg.extra.get("key")
            or os.getenv("AWS_ACCESS_KEY_ID")
            or os.getenv("VOODOO_S3_KEY")
            or ""
        )
        secret_key = (
            cfg.extra.get("secret")
            or os.getenv("AWS_SECRET_ACCESS_KEY")
            or os.getenv("VOODOO_S3_SECRET")
            or ""
        )
        region = os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION", "us-east-1")
        root_prefix = cfg.extra.get("root_prefix") or ""
        return S3ObjectStore(
            bucket=bucket,
            key=access_key,
            secret=secret_key,
            region=region,
            endpoint=endpoint or None,
            root_prefix=root_prefix,
        )

    def _create_memory_cache(self, cfg: CacheConfig) -> Any:
        from voodoo.storage.cache.memory import MemoryCache

        return MemoryCache()

    def _create_redis_cache(self, cfg: CacheConfig) -> Any:
        """Build a :class:`~voodoo.storage.cache.redis.RedisCache`.

        URL resolution order (Sprint 13):
        1. ``cfg.url`` from ``voodoo.yaml`` (``cache.url``);
        2. ``VOODOO_CACHE_URL`` environment variable;
        3. ``VOODOO_REDIS_URL`` environment variable;
        4. parts in ``cfg.extra`` (``host``/``port``/``db``);
        5. ``redis://localhost:6379/0``.

        Raises a clear ``ConfigurationError`` when the ``[redis]`` extra is
        not installed (lazy import, mirrors the postgres factory).
        """
        import os

        from voodoo.storage.cache.redis import RedisCache

        url = (
            cfg.url
            or os.getenv("VOODOO_CACHE_URL")
            or os.getenv("VOODOO_REDIS_URL")
            or ""
        )
        if not url:
            host = cfg.extra.get("host") or "localhost"
            port = cfg.extra.get("port") or "6379"
            db = cfg.extra.get("db") or "0"
            url = f"redis://{host}:{port}/{db}"
        return RedisCache(url)


# Global provider registry instance
registry = ProviderRegistry()
