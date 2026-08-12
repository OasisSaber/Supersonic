# G4 Slice A Persistence Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立 PostgreSQL 持久化基础，包括配置、异步 engine/session factory、领域侧持久化 Port、SQLAlchemy Adapter、Alembic 初始迁移、Repository/Unit of Work、显式集成测试入口与 CI PostgreSQL service，同时保持现有 Cockpit Runtime、`gp05.v1` 和默认本地验证完全不依赖数据库。

**Architecture:** `app.platform` 只保存框架无关的 User、Platform Session、AuditEvent 数据语义和内部持久化 Protocol；`app.adapters.postgres` 保存 SQLAlchemy ORM、映射、Repository 与 Unit of Work。Alembic 复用同一 ORM metadata，但不创建用户、密码或 Cockpit Runtime 表。每个 Unit of Work 创建独立 `AsyncSession`，只显式提交，不在 import、应用启动或现有 Router 中隐式连接 PostgreSQL。

**Tech Stack:** Python 3.11、SQLAlchemy 2.0 async、Psycopg 3 binary、Alembic 1.18、PostgreSQL 18、pytest/pytest-asyncio、uv、pnpm、GitHub Actions、Jujutsu。

## Global Constraints

- 本计划只覆盖已批准 G3 设计中的 Slice A：依赖、配置、engine/session factory、ORM、Alembic、Repository、Unit of Work、迁移/约束/事务集成测试和 CI 数据库服务。
- 执行前必须从已经包含 G3 批准文档的最新 `main` 创建独立 Issue 或取得等价的明确人类授权，并创建一个新的 jj change 与短生命周期 bookmark。不得在 `codex/issue-47-g3-architecture-review` 上实现本计划。
- 本计划及“批准 G3 书面规格”都不授权 push、创建或更新 PR、Ready、merge、release、force-push、远端删除或仓库设置变更。首次远端影响仍需满足 `core/policy.md` 的完整任务级授权。
- 不接 Router，不修改 `app.main` composition，不实现密码散列、登录、cookie、Origin、SessionService、审计运行时 sink/reconciliation、命令 Gateway 接线、WebSocket 撤销、seed CLI 或 UI。
- `CockpitService` 继续是车辆、导航、风险、媒体、Cockpit Session 和 snapshot 的唯一实时权威。不得创建对应 PostgreSQL 表，也不得让 snapshot/广播路径查询数据库。
- `app.platform` 不导入 FastAPI、SQLAlchemy、Psycopg 或 Alembic；ORM 与数据库异常不得泄露到领域模型或公开 API。
- `DATABASE_URL` 缺失时合法且不触发连接；`pnpm check`、`bash scripts/validate.sh` 与 `pnpm smoke:gp05` 必须继续在无 PostgreSQL 环境中通过。
- PostgreSQL 集成测试只通过显式 `TEST_DATABASE_URL` 运行；缺失、驱动不为 `postgresql+psycopg` 或数据库名不以 `_test` 结尾时必须失败而不是跳过。
- raw Platform Session secret 不得进入领域记录、ORM、迁移、日志或测试 fixture；数据库只保存 64 字符小写十六进制 SHA-256 digest。
- 所有时间字段使用 timezone-aware UTC `datetime` 与 PostgreSQL `TIMESTAMPTZ`。User、Platform Session、AuditEvent 主键和 `actor_platform_session_id` 使用 PostgreSQL UUID，并在 Adapter 边界与领域 `str` ID 互相转换；`cockpit_session_id` 保持现有最多 80 字符的 Cockpit 合同，不强制改为 UUID。
- 初始迁移只创建 `users`、`platform_sessions`、`audit_events`、约束与索引；不创建默认管理员、不写密码、不创建 Cockpit Runtime 状态表。
- 一个请求/任务对应一个 `AsyncSession`；不得跨 asyncio task 共享 Session，不自动提交，不构造 PostgreSQL 与内存 Cockpit Runtime 的伪分布式事务。

---

## File Structure

### New files

- `apps/backend/app/platform/persistence.py` — 框架无关的持久化 Protocol 与 Unit of Work 合同。
- `apps/backend/app/adapters/__init__.py` — 出站 Adapter 包边界。
- `apps/backend/app/adapters/postgres/__init__.py` — PostgreSQL Adapter 的窄导出。
- `apps/backend/app/adapters/postgres/database.py` — async engine/session factory；不保存全局 engine。
- `apps/backend/app/adapters/postgres/orm.py` — `Base`、`UserRow`、`PlatformSessionRow`、`AuditEventRow` 与命名约束。
- `apps/backend/app/adapters/postgres/repositories.py` — 领域记录与 ORM Row 映射、三个 Repository Adapter。
- `apps/backend/app/adapters/postgres/unit_of_work.py` — 每次进入创建独立 `AsyncSession` 的显式 UoW。
- `apps/backend/alembic.ini` — Alembic 配置，script location 以配置文件目录为基准。
- `apps/backend/migrations/env.py` — async Alembic 环境，metadata 来自 PostgreSQL Adapter。
- `apps/backend/migrations/script.py.mako` — Alembic revision 模板。
- `apps/backend/migrations/versions/20260809_0001_platform_foundation.py` — 手写、可逆的初始 schema。
- `apps/backend/integration_tests/conftest.py` — 强制安全测试 DSN、重建测试 schema、迁移到 head、逐测试清表。
- `apps/backend/integration_tests/test_migrations.py` — 空库到 head、表/列/约束/索引与 downgrade/upgrade。
- `apps/backend/integration_tests/test_constraints.py` — PostgreSQL unique/check/FK/UUID/TIMESTAMPTZ/JSONB 约束。
- `apps/backend/integration_tests/test_repositories.py` — Repository 映射、显式 commit/rollback 与审计幂等写入。
- `apps/backend/tests/test_platform_persistence_contracts.py` — 领域记录和 Port 的框架隔离单元测试。
- `apps/backend/tests/test_postgres_database.py` — engine/session factory 无隐式连接与 Session 隔离单元测试。
- `apps/backend/tests/test_postgres_metadata.py` — 无数据库的 metadata 结构测试。

### Modified files

- `apps/backend/pyproject.toml` — 锁定 SQLAlchemy、Alembic 与 Psycopg 版本范围。
- `uv.lock` — 由 `uv lock` 机械更新。
- `apps/backend/app/config.py` — 添加可选 `database_url`，保持环境变量优先级与无数据库默认值。
- `apps/backend/app/platform/models.py` — 添加框架无关的 `User`、`PlatformSession`、`AuditEvent`；保留现有 `Principal`/`AuditRecord` 兼容性。
- `apps/backend/tests/test_config.py` — 数据库配置优先级、空值和健康响应保密测试。
- `package.json` — 添加唯一的显式 PostgreSQL 集成测试命令。
- `.github/workflows/check.yml` — 添加 PostgreSQL 18.4 service，并在现有验证后强制运行集成测试。
- `.env.example` — 只增加注释形式的本地 `DATABASE_URL` 示例，不提供真实凭据。
- `docs/development.md` — 记录无数据库默认验证、显式本地集成测试和 CI 含义。

---

## Task 1: Lock dependencies and add an inert database configuration contract

**Files:**

- Modify: `apps/backend/pyproject.toml`
- Modify: `uv.lock`
- Modify: `apps/backend/app/config.py`
- Modify: `apps/backend/tests/test_config.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    app_mode: AppMode = AppMode.MOCK
    control_enabled: bool = False
    database_url: str | None = None
```

`load_settings()` 继续使用“进程环境覆盖根 `.env`”规则。`DATABASE_URL` 缺失或仅含空白时归一化为 `None`；本 Slice 不校验数据库可达性，也不在健康接口返回该值。

- [ ] **Step 1: Write failing configuration tests**

在 `apps/backend/tests/test_config.py` 增加以下行为测试：

```python
def test_database_url_is_optional(tmp_path: Path) -> None:
    settings = load_settings(env_file=tmp_path / ".env", environ={})

    assert settings.database_url is None


def test_process_database_url_overrides_root_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://file_user:file_pass@db/file_db\n",
        encoding="utf-8",
    )

    settings = load_settings(
        env_file=env_file,
        environ={
            "DATABASE_URL": "postgresql+psycopg://process_user:process_pass@db/process_db"
        },
    )

    assert settings.database_url == (
        "postgresql+psycopg://process_user:process_pass@db/process_db"
    )


def test_blank_database_url_is_treated_as_unconfigured(tmp_path: Path) -> None:
    settings = load_settings(
        env_file=tmp_path / ".env",
        environ={"DATABASE_URL": "   "},
    )

    assert settings.database_url is None
```

扩展现有 health 测试，使 `.env` 同时包含带凭据的 `DATABASE_URL`，并继续断言响应严格等于 `{"status": "ok", "mode": "mock"}`。

- [ ] **Step 2: Run the focused test and observe the expected failure**

Run:

```powershell
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/tests/test_config.py -q
```

Expected: 新测试因 `RuntimeSettings` 没有 `database_url` 而失败；原测试保持通过。

- [ ] **Step 3: Add supported persistence dependencies**

在 `apps/backend/pyproject.toml` 的主依赖中增加：

```toml
"sqlalchemy>=2.0.51,<2.1",
"alembic>=1.18.5,<1.19",
"psycopg[binary]>=3.3.4,<3.4",
```

这些范围固定 SQLAlchemy 2.0 API、Alembic 1.18 次版本与 Psycopg 3.3 次版本；不增加 `psycopg_pool`，连接池由 SQLAlchemy engine 管理。

- [ ] **Step 4: Implement optional configuration without I/O**

在 `load_settings()` 中按现有优先级读取 `DATABASE_URL`，使用一个纯函数将空白值转换为 `None`，并写入 `RuntimeSettings.database_url`。禁止创建 engine、解析密码到日志或探测网络。

- [ ] **Step 5: Refresh the lockfile and run focused validation**

Run:

```powershell
uv lock --project apps/backend
uv sync --locked --project apps/backend
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/tests/test_config.py -q
uv --cache-dir .uv-cache run --project apps/backend --no-sync ruff check apps/backend/app/config.py apps/backend/tests/test_config.py
```

Expected: lock/sync 成功；配置测试全部通过；Ruff 无诊断。

- [ ] **Step 6: Inspect the Slice change without creating another jj change**

Run:

```powershell
jj status
jj diff --stat
jj diff apps/backend/pyproject.toml apps/backend/app/config.py apps/backend/tests/test_config.py
```

Expected: 只包含本任务文件和机械生成的 `uv.lock` 更新；不出现 Router 或 `app.main` 修改。

## Task 2: Define framework-free persistence records and ports

**Files:**

- Modify: `apps/backend/app/platform/models.py`
- Create: `apps/backend/app/platform/persistence.py`
- Create: `apps/backend/tests/test_platform_persistence_contracts.py`

**Interfaces:**

```python
@dataclass(frozen=True, slots=True)
class User:
    id: str
    username_norm: str
    display_name: str
    password_hash: str
    role: Role
    disabled_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class PlatformSession:
    id: str
    user_id: str
    token_digest: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime | None = None
    revoked_at: datetime | None = None
    revoke_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AuditEvent:
    id: str
    occurred_at: datetime
    action: str
    result: AuditResult
    delivery: AuditDelivery
    actor_user_id: str | None = None
    actor_platform_session_id: str | None = None
    actor_role: Role | None = None
    endpoint: str | None = None
    cockpit_session_id: str | None = None
    command_name: str | None = None
    correlation_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None
    source_type: str = "local_hmi"
```

`apps/backend/app/platform/persistence.py` 定义：

```python
class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...
    async def get_by_id(self, user_id: str) -> User | None: ...
    async def get_by_username_norm(self, username_norm: str) -> User | None: ...


class PlatformSessionRepository(Protocol):
    async def add(self, platform_session: PlatformSession) -> None: ...
    async def get_by_token_digest(self, token_digest: str) -> PlatformSession | None: ...


class AuditEventRepository(Protocol):
    async def append(self, event: AuditEvent) -> bool: ...


class PlatformUnitOfWork(Protocol):
    users: UserRepository
    platform_sessions: PlatformSessionRepository
    audit_events: AuditEventRepository

    async def __aenter__(self) -> Self: ...
    async def __aexit__(self, exc_type, exc, traceback) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

`AuditEventRepository.append()` 返回 `True` 表示插入，返回 `False` 表示同一 UUID 已存在；它不把 `lost` 持久化为 Row。后续 Slice B/C 可以在不暴露 SQLAlchemy 的情况下扩展内部 Port。

- [ ] **Step 1: Write failing isolation and shape tests**

测试构造三个记录，确认 Platform Session 只含 `token_digest`、不存在 `token`/`secret` 字段，并通过 AST/import 检查确保 `app.platform.models` 与 `app.platform.persistence` 不引用 `fastapi`、`sqlalchemy`、`psycopg` 或 `alembic`：

```python
def test_platform_session_model_has_no_raw_secret_field() -> None:
    field_names = {item.name for item in fields(PlatformSession)}

    assert "token_digest" in field_names
    assert "token" not in field_names
    assert "secret" not in field_names


@pytest.mark.parametrize("module_name", ["models.py", "persistence.py"])
def test_platform_core_has_no_framework_imports(module_name: str) -> None:
    source = (PLATFORM_DIR / module_name).read_text(encoding="utf-8")

    assert "sqlalchemy" not in source
    assert "psycopg" not in source
    assert "alembic" not in source
    assert "fastapi" not in source
```

- [ ] **Step 2: Run the test and observe import failures**

Run:

```powershell
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/tests/test_platform_persistence_contracts.py -q
```

Expected: collection fails because the new records/ports do not exist.

- [ ] **Step 3: Add records and Protocols without changing public runtime exports**

实现上述数据类和 Protocol。保留现有 `AuditRecord`、`Principal` 与 `app.platform.__init__` 导出，以免 Slice A 改变当前 Gateway 行为。不得在数据类 `__post_init__` 中加入数据库或认证策略；持久化约束由 Adapter/数据库负责，业务策略留给后续 Slice。

- [ ] **Step 4: Run focused tests and lint**

Run:

```powershell
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/tests/test_platform_persistence_contracts.py apps/backend/tests/test_platform_gateway.py -q
uv --cache-dir .uv-cache run --project apps/backend --no-sync ruff check apps/backend/app/platform apps/backend/tests/test_platform_persistence_contracts.py
```

Expected: 新合同测试和现有 Gateway 测试通过；无框架导入与 Ruff 诊断。

## Task 3: Add the PostgreSQL engine/session factory and ORM metadata

**Files:**

- Create: `apps/backend/app/adapters/__init__.py`
- Create: `apps/backend/app/adapters/postgres/__init__.py`
- Create: `apps/backend/app/adapters/postgres/database.py`
- Create: `apps/backend/app/adapters/postgres/orm.py`
- Create: `apps/backend/tests/test_postgres_database.py`
- Create: `apps/backend/tests/test_postgres_metadata.py`

**Interfaces:**

```python
def create_database_engine(database_url: str, *, echo: bool = False) -> AsyncEngine: ...


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]: ...
```

`create_database_engine()` 只接受 `postgresql+psycopg` URL，使用 `pool_pre_ping=True`，不得 connect。`create_session_factory()` 使用 `expire_on_commit=False`、`autoflush=False`，每次调用 factory 返回独立 Session。模块内不得创建全局 engine/session factory。

ORM metadata 使用固定命名 convention：`ix_`、`uq_`、`ck_`、`fk_`、`pk_`。三个 Row 的字段必须逐一匹配 G3 第 6 节；所有 PostgreSQL UUID 使用 `UUID(as_uuid=True)`，JSON 使用 `JSONB`，时间使用 `DateTime(timezone=True)`。

列类型和长度固定如下，ORM 与 migration 必须相同：

| 表 | 列 | PostgreSQL/SQLAlchemy 类型 | Null |
| --- | --- | --- | --- |
| `users` | `id` | UUID | no |
| `users` | `username_norm` | VARCHAR(128) | no |
| `users` | `display_name` | VARCHAR(128) | no |
| `users` | `password_hash` | TEXT | no |
| `users` | `role` | VARCHAR(16) | no |
| `users` | `disabled_at` | TIMESTAMPTZ | yes |
| `users` | `created_at`, `updated_at` | TIMESTAMPTZ | no |
| `platform_sessions` | `id`, `user_id` | UUID | no |
| `platform_sessions` | `token_digest` | CHAR(64) | no |
| `platform_sessions` | `created_at`, `expires_at` | TIMESTAMPTZ | no |
| `platform_sessions` | `last_seen_at`, `revoked_at` | TIMESTAMPTZ | yes |
| `platform_sessions` | `revoke_reason` | VARCHAR(128) | yes |
| `audit_events` | `id` | UUID | no |
| `audit_events` | `occurred_at` | TIMESTAMPTZ | no |
| `audit_events` | `action` | VARCHAR(128) | no |
| `audit_events` | `result`, `delivery` | VARCHAR(16) | no |
| `audit_events` | `actor_role` | VARCHAR(16) | yes |
| `audit_events` | `actor_user_id`, `actor_platform_session_id` | UUID | yes |
| `audit_events` | `endpoint` | VARCHAR(32) | yes |
| `audit_events` | `source_type` | VARCHAR(32) | no |
| `audit_events` | `cockpit_session_id` | VARCHAR(80) | yes |
| `audit_events` | `command_name`, `error_code`, `target_type` | VARCHAR(64) | yes |
| `audit_events` | `correlation_id` | VARCHAR(64) | yes |
| `audit_events` | `target_id` | VARCHAR(128) | yes |
| `audit_events` | `parameters` | JSONB | no |

`source_type` 必须非空并由应用显式提供，领域默认值为 `local_hmi`；数据库不使用会掩盖应用遗漏的业务默认值。`parameters` 可使用数据库空对象默认值，但 Adapter 仍总是显式写入 sanitize 后的对象。

约束至少包括：

- `users.username_norm` unique、非空且长度 1–128；`role` 只能是 `admin/operator/viewer`；`display_name` 长度 1–128；
- `platform_sessions.user_id` 使用 `ON DELETE RESTRICT`；`token_digest` unique 且匹配 `^[0-9a-f]{64}$`；`expires_at > created_at`；`revoke_reason` 最长 128；
- `audit_events.actor_user_id` 可空并使用 `ON DELETE RESTRICT`；`actor_platform_session_id` 只是 UUID 历史值、无 FK；`result` 只能是 `attempted/succeeded/rejected/error`；`delivery` 只能是 `primary/fallback`；`parameters` 为非空 JSONB；
- `audit_events` 建立 `(occurred_at DESC, id DESC)` 索引；不得给 Cockpit Runtime 字段建表。

- [ ] **Step 1: Write failing engine and metadata tests**

```python
async def test_session_factory_returns_distinct_sessions_without_connecting() -> None:
    engine = create_database_engine(
        "postgresql+psycopg://user:password@127.0.0.1:1/supersonic_test"
    )
    factory = create_session_factory(engine)

    first = factory()
    second = factory()
    try:
        assert first is not second
        assert first.bind is engine
        assert second.bind is engine
    finally:
        await first.close()
        await second.close()
        await engine.dispose()


def test_metadata_contains_only_platform_tables() -> None:
    assert set(Base.metadata.tables) == {
        "users",
        "platform_sessions",
        "audit_events",
    }
```

补充测试必须验证列类型、nullability、FK/on-delete、unique/check 约束、审计 actor session 无 FK，以及所有 DateTime 均 `timezone=True`。

- [ ] **Step 2: Run the tests and observe missing-module failures**

Run:

```powershell
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/tests/test_postgres_database.py apps/backend/tests/test_postgres_metadata.py -q
```

Expected: collection fails because Adapter modules do not exist。

- [ ] **Step 3: Implement engine/session factory and metadata**

使用 SQLAlchemy 2.0 typed declarative mapping：

```python
class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UserRow(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    username_norm: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
```

实际实现必须声明本任务字段清单中的全部字段、约束与索引。

- [ ] **Step 4: Run focused tests and lint**

Run:

```powershell
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/tests/test_postgres_database.py apps/backend/tests/test_postgres_metadata.py -q
uv --cache-dir .uv-cache run --project apps/backend --no-sync ruff check apps/backend/app/adapters apps/backend/tests/test_postgres_database.py apps/backend/tests/test_postgres_metadata.py
```

Expected: 所有测试通过，且端口 `1` 上没有实际连接尝试。

## Task 4: Add a deterministic async Alembic environment and initial migration

**Files:**

- Create: `apps/backend/alembic.ini`
- Create: `apps/backend/migrations/env.py`
- Create: `apps/backend/migrations/script.py.mako`
- Create: `apps/backend/migrations/versions/20260809_0001_platform_foundation.py`
- Create: `apps/backend/integration_tests/conftest.py`
- Create: `apps/backend/integration_tests/test_migrations.py`

**Interfaces and migration contract:**

- `apps/backend/alembic.ini` 使用 `script_location = %(here)s/migrations` 与 `prepend_sys_path = %(here)s`；配置文件中不保存数据库凭据。
- `env.py` 从 `DATABASE_URL` 读取迁移 URL，要求 `postgresql+psycopg`，将 URL 直接传给 `async_engine_from_config()`，并通过 `connection.run_sync(do_run_migrations)` 执行在线迁移。
- 离线模式可生成 SQL，但不得把完整 DSN 输出到日志。
- revision 固定为 `20260809_0001`，`down_revision = None`；`upgrade()` 手写创建三张表和索引，`downgrade()` 以 `audit_events`、`platform_sessions`、`users` 顺序删除。
- migration 结构必须与 `Base.metadata` 一致；不通过运行时 `metadata.create_all()` 替代 migration。

- [ ] **Step 1: Write a failing integration harness and migration test**

`apps/backend/integration_tests/conftest.py` 在 pytest 启动时执行：

```python
def require_test_database_url() -> str:
    raw_url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not raw_url:
        raise pytest.UsageError("TEST_DATABASE_URL is required for PostgreSQL integration tests")
    url = make_url(raw_url)
    if url.drivername != "postgresql+psycopg":
        raise pytest.UsageError("TEST_DATABASE_URL must use postgresql+psycopg")
    if not url.database or not url.database.endswith("_test"):
        raise pytest.UsageError("TEST_DATABASE_URL database name must end with _test")
    return raw_url
```

session fixture 只在上述 guard 通过后，对这个明确测试库执行 `DROP SCHEMA public CASCADE`、`CREATE SCHEMA public`，将 `DATABASE_URL` 临时设置为相同测试 DSN，并调用 Alembic Python API upgrade 到 `head`。测试结束不删除数据库，只清理 schema。该破坏性动作不得接受 `DATABASE_URL` fallback。

`test_migrations.py` 必须证明：

1. 空 schema 能 upgrade 到唯一 head；
2. `alembic_version` 为 `20260809_0001`；
3. 仅存在三张平台业务表及 Alembic 版本表；
4. downgrade 到 base 后三张业务表均消失；再次 upgrade head 后恢复；
5. ORM metadata 与实库的表、列、nullable、FK 和 unique/check 名称一致。

- [ ] **Step 2: Run without a DSN and verify fail-closed behavior**

Run:

```powershell
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/integration_tests/test_migrations.py -q
```

Expected: pytest 以 usage error 非零退出，消息明确要求 `TEST_DATABASE_URL`；不得显示 skipped。

- [ ] **Step 3: Implement Alembic files and the hand-written revision**

创建完整 async `env.py` 与 revision。revision 中使用显式 constraint/index 名称，不调用应用 service，不生成默认管理员，也不读取 `.env`。`DATABASE_URL` 只通过执行进程传入。

- [ ] **Step 4: Run against an explicitly provisioned local test database**

Prerequisite: 开发者已经自行提供名为 `supersonic_test` 的 PostgreSQL 数据库。Run:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://supersonic:supersonic_test@127.0.0.1:5432/supersonic_test'
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/integration_tests/test_migrations.py -q
```

Expected: migration 测试全部通过。若本机没有数据库，此步骤如实记录为未运行，不能用 unit test 代替；CI 仍必须执行它。

## Task 5: Implement PostgreSQL repositories and explicit Unit of Work

**Files:**

- Create: `apps/backend/app/adapters/postgres/repositories.py`
- Create: `apps/backend/app/adapters/postgres/unit_of_work.py`
- Modify: `apps/backend/app/adapters/postgres/__init__.py`
- Create: `apps/backend/integration_tests/test_repositories.py`

**Interfaces:**

```python
class SqlAlchemyUserRepository(UserRepository): ...
class SqlAlchemyPlatformSessionRepository(PlatformSessionRepository): ...
class SqlAlchemyAuditEventRepository(AuditEventRepository): ...


class SqlAlchemyPlatformUnitOfWork(PlatformUnitOfWork):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None: ...
```

Mapping rules:

- Adapter 使用 `UUID(value)` 写入，并用 `str(row.id)` 返回领域 ID；无效 UUID 在 Adapter 边界明确失败。
- User 与 Platform Session 使用普通 typed `select()`；token 查询只接受 digest。
- AuditEvent 使用 PostgreSQL `insert(...).on_conflict_do_nothing(index_elements=[AuditEventRow.id])` 并以 `rowcount == 1` 表示首次插入。
- `AuditDelivery.LOST` 在发 SQL 前抛出 `ValueError`，因为 lost 没有持久化介质。
- UoW `__aenter__` 创建 Session 和三个 Repository；`commit()`/`rollback()` 显式委托；`__aexit__` 在异常或未提交时 rollback，最后 close。不得隐式 commit。

- [ ] **Step 1: Write failing repository transaction tests**

```python
async def test_uow_requires_explicit_commit(
    session_factory: async_sessionmaker[AsyncSession],
    sample_user: User,
) -> None:
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        await uow.users.add(sample_user)

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as verification:
        assert await verification.users.get_by_id(sample_user.id) is None


async def test_audit_append_is_idempotent(
    session_factory: async_sessionmaker[AsyncSession],
    sample_audit_event: AuditEvent,
) -> None:
    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        assert await uow.audit_events.append(sample_audit_event) is True
        await uow.commit()

    async with SqlAlchemyPlatformUnitOfWork(session_factory) as uow:
        assert await uow.audit_events.append(sample_audit_event) is False
        await uow.commit()
```

还必须测试：User add/get 映射、username lookup、Platform Session add/digest lookup、显式 commit 保留数据、异常 rollback、每个并发 UoW 使用不同 AsyncSession、`lost` delivery 在 SQL 前被拒绝。

- [ ] **Step 2: Run and observe missing Adapter failures**

Run with the explicit safe test DSN:

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://supersonic:supersonic_test@127.0.0.1:5432/supersonic_test'
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/integration_tests/test_repositories.py -q
```

Expected: collection fails because Repository/UoW classes do not exist。

- [ ] **Step 3: Implement mapping, repositories and UoW**

实现完整双向映射。Repository 不执行 commit，UoW 不暴露原始 Session 为公共属性。`__aexit__` 必须通过测试证明不会把未提交写入泄漏到后续 UoW。

- [ ] **Step 4: Run repository integration tests and focused lint**

```powershell
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/integration_tests/test_repositories.py -q
uv --cache-dir .uv-cache run --project apps/backend --no-sync ruff check apps/backend/app/adapters apps/backend/integration_tests
```

Expected: 所有映射、commit/rollback、Session 隔离和幂等测试通过；Ruff 无诊断。

## Task 6: Prove database constraints against PostgreSQL

**Files:**

- Create: `apps/backend/integration_tests/test_constraints.py`
- Modify: `apps/backend/integration_tests/conftest.py`

- [ ] **Step 1: Write direct database constraint tests**

测试必须直接 insert 非法 Row 并捕获 `sqlalchemy.exc.IntegrityError`，而不是只检查 metadata：

- 重复 `username_norm` 被 unique 拒绝；
- 非 `admin/operator/viewer` role 被 check 拒绝；
- 重复或非 64 位小写十六进制 `token_digest` 被拒绝；
- 缺失 User 的 Platform Session 被 FK 拒绝；
- 有 Platform Session 的 User 删除被 `ON DELETE RESTRICT` 拒绝；
- `expires_at <= created_at` 被拒绝；
- Audit `lost` delivery、非法 result 被拒绝；
- Audit actor User 引用阻止删除 User；
- Audit actor Platform Session ID 可以引用不存在或已清理的 UUID；
- JSONB parameters、timezone-aware timestamps 和 `(occurred_at, id)` 索引真实存在；
- 实库列名中不存在 `raw_secret`、`token`、`password`，只允许 `password_hash` 与 `token_digest`。

每次期望的 IntegrityError 后必须显式 rollback，避免污染后续断言。

- [ ] **Step 2: Run the tests and observe failures before finalizing constraints**

```powershell
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/integration_tests/test_constraints.py -q
```

Expected: 尚未被 ORM/migration 同时实现的约束产生测试失败。

- [ ] **Step 3: Align ORM metadata and migration**

只修正 `orm.py` 与初始 revision 的同名约束/索引；不得只在测试中模拟数据库约束。由于初始 revision 尚未发布，直接保持其确定性内容一致；一旦本 Slice revision 已 push，后续修正必须新增 revision，不得重写已发布历史。

- [ ] **Step 4: Run the complete integration suite**

```powershell
uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/integration_tests -q
```

Expected: migration、Repository、事务和约束测试全部通过且没有 skip。

## Task 7: Make PostgreSQL integration explicit locally and mandatory in CI

**Files:**

- Modify: `package.json`
- Modify: `.github/workflows/check.yml`
- Modify: `.env.example`
- Modify: `docs/development.md`

**Command contract:**

在 `package.json` 增加：

```json
"test:backend:integration": "uv --cache-dir .uv-cache run --project apps/backend --no-sync pytest apps/backend/integration_tests -q"
```

现有 `test:backend` 和 `pnpm check` 不包含 integration_tests。

CI `check` job 增加：

```yaml
services:
  postgres:
    image: postgres:18.4-alpine
    env:
      POSTGRES_USER: supersonic
      POSTGRES_PASSWORD: supersonic_test
      POSTGRES_DB: supersonic_test
    ports:
      - 5432:5432
    options: >-
      --health-cmd "pg_isready -U supersonic -d supersonic_test"
      --health-interval 10s
      --health-timeout 5s
      --health-retries 5
```

并在 `Validate` 后、GP05 smoke 前加入不可跳过步骤：

```yaml
- name: Run PostgreSQL integration tests
  env:
    TEST_DATABASE_URL: postgresql+psycopg://supersonic:supersonic_test@127.0.0.1:5432/supersonic_test
  run: pnpm test:backend:integration
```

- [ ] **Step 1: Add a command-contract failure check**

先运行尚未存在的命令：

```powershell
pnpm test:backend:integration
```

Expected: pnpm 报告 script 不存在；不得把该结果误报为数据库测试失败。

- [ ] **Step 2: Add script, CI service and documentation**

`.env.example` 只加入注释示例：

```dotenv
# G4 平台持久化；缺失时现有 Mock HMI 继续无数据库运行。
# DATABASE_URL=postgresql+psycopg://supersonic:replace-me@127.0.0.1:5432/supersonic
```

`docs/development.md` 必须记录：

- `DATABASE_URL` 是未来 composition 使用的可选运行配置，本 Slice 不接 Router；
- `TEST_DATABASE_URL` 只供显式集成测试，目标库名必须以 `_test` 结尾，测试会重建其 `public` schema；
- 本地不要求 Docker，开发者可使用自行提供的 PostgreSQL；
- `pnpm check`/`scripts/validate.sh` 无数据库，`pnpm test:backend:integration` 有数据库；
- CI 使用临时 PostgreSQL 18.4 并强制运行集成测试；
- migration/CI 通过不代表登录、RBAC、审计运行时、UI、LAN HTTPS、备份恢复或部署已经完成。

- [ ] **Step 3: Validate YAML, JSON and fail-closed local command**

Run:

```powershell
node -e "JSON.parse(require('fs').readFileSync('package.json','utf8')); console.log('package.json valid')"
python -c "from pathlib import Path; import yaml; yaml.safe_load(Path('.github/workflows/check.yml').read_text(encoding='utf-8')); print('workflow YAML valid')"
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
pnpm test:backend:integration
```

Expected: formatting check 通过；集成命令因缺少 `TEST_DATABASE_URL` 非零退出并且没有 skip。

- [ ] **Step 4: Run the explicit integration command with the safe test DSN**

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://supersonic:supersonic_test@127.0.0.1:5432/supersonic_test'
pnpm test:backend:integration
```

Expected: 全部 PostgreSQL 集成测试通过且没有 skip。

## Task 8: Full verification, self-review and local jj handoff

**Files:** all Slice A files listed above.

- [ ] **Step 1: Run framework and secret-boundary scans**

```powershell
rg -n "from (fastapi|sqlalchemy|psycopg|alembic)|import (fastapi|sqlalchemy|psycopg|alembic)" apps/backend/app/platform
rg -n "raw_secret|raw_token|session_secret" apps/backend/app apps/backend/migrations apps/backend/integration_tests
rg -n "CockpitService|snapshot|cockpit_state|vehicle|navigation|risk|media" apps/backend/app/adapters/postgres apps/backend/migrations
```

Expected: 第一个和第二个扫描无匹配；第三个扫描无持久化 Cockpit Runtime 的实现匹配。测试断言文本若产生匹配，必须人工确认只是在禁止性断言中出现。

- [ ] **Step 2: Run all local database-free validation**

```powershell
pnpm lint:backend
pnpm test:backend
pnpm check
& 'C:\Program Files\Git\bin\bash.exe' scripts/validate.sh
pnpm smoke:gp05
```

Expected: Ruff、全部现有单元测试、前端测试/构建、仓库验证和真实 GP05 进程 smoke 全部通过；运行这些命令时不设置 `DATABASE_URL` 或 `TEST_DATABASE_URL`。

- [ ] **Step 3: Run the mandatory PostgreSQL verification**

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://supersonic:supersonic_test@127.0.0.1:5432/supersonic_test'
pnpm test:backend:integration
```

Expected: migration、约束、Repository 和事务测试全部通过且没有 skip。若本机无法提供 PostgreSQL，应记录本地未覆盖，并等待 CI；不得声称本地集成测试通过。

- [ ] **Step 4: Inspect the complete change and verify exact scope**

```powershell
jj status
jj diff --stat
jj diff
git diff --check
```

人工逐文件确认：

- 只有本计划列出的 Slice A 文件；
- 没有 Router、`app.main`、前端、合同或 Cockpit Runtime 变更；
- 没有真实 DSN、密码、cookie、raw secret、日志样本、缓存、构建产物或临时文件；
- migration 与 ORM metadata 同名且字段/约束一致；
- `pnpm check` 无数据库，CI integration 不可跳过；
- 验证记录不把 migration/CI 冒充运行时身份、UI、部署或备份恢复证据。

- [ ] **Step 5: Describe the single jj change and create a clean child**

```powershell
jj describe -m "feat(platform): add PostgreSQL persistence foundation"
jj new
jj status
jj log -n 3
```

Expected: Slice A 全部实现位于一个已描述 change；新的 working copy 是空 child。只有在任务级远端授权已经明确记录远端、Issue、bookmark、base、文件范围、push/PR 权限，且完整 diff 与所有要求验证均通过后，才可进入 push/PR 流程。

---

## Spec Coverage Review

- G3 §5：framework-free `app.platform` + PostgreSQL Adapter + 明确 UoW；未接 composition root/Router。
- G3 §6：三表、UUID、UTC timestamptz、单角色、soft-disable 字段、digest-only Session、审计 actor FK 语义、JSONB、幂等 UUID。
- G3 §6.4：Alembic schema only、无默认管理员、无 Cockpit Runtime 表。
- G3 D14：默认本地验证无 PostgreSQL；显式 `TEST_DATABASE_URL`；CI 强制临时 PostgreSQL。
- G3 D15：每 UoW/任务独立 AsyncSession、显式 commit/rollback、无伪分布式事务。
- Slice 边界：密码/登录/SessionService 留给 B；审计 sink/query/reconciliation 留给 C；Router/命令/WS 留给 D；演示/恢复证据留给 E。

## Primary References

- [G3 approved architecture](../../design/2026-08-09-g3-platform-architecture-design.md)
- [ADR 0001](../../adr/0001-postgresql-platform-boundary.md)
- [Project decision baseline](../../project/DECISION_BASELINE.md)
- [SQLAlchemy 2.0 documentation](https://docs.sqlalchemy.org/en/20/)
- [SQLAlchemy Psycopg dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html)
- [Alembic documentation](https://alembic.sqlalchemy.org/en/latest/front.html)
- [Psycopg binary installation guidance](https://www.psycopg.org/psycopg3/docs/basic/install.html)
- [PostgreSQL versioning policy](https://www.postgresql.org/support/versioning/)
