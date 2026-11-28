# Series-Wide Optimization Review & Execution Plan

> **Scope:** Internal engineering review and phased execution roadmap for the `rusty-conduit-series` workspace and its five member repositories (`rusty-conduit-engine` `v0.6.0`, `rusty-conduit` `v2.3.0`, `rusty-conduit-ssh` `v2.3.0`, `rusty-conduit-switch` `v2.3.0`, and `rusty-conduit-gui`). For workspace setup and cross-repo rules, see [WORKSPACE.md](WORKSPACE.md) and [DOX.md](../DOX.md).

---

## 1. Adopted Architectural Decisions & Invariants

### Fixed Product Invariants (Must Not Regress)
1. **Zero hidden data/DNS/connection caches:** Never cache HTTP responses, DNS lookups, or upstream client connections (`CertCache` remains the sole cache in `rusty-conduit-engine`).
2. **Pure-Rust cryptography:** Keep `rustls` (`ring`) + `rcgen` + `russh` across every target; `openssl-sys` and `aws-lc-sys` must never enter `Cargo.lock`.
3. **Engine-first release discipline:** Any change in `rusty-conduit-engine` that alters observable behavior or public API is recorded in `rusty-conduit-engine/docs/DIVERGENCE-LEDGER.md`, verified with `--locked` and `--no-default-features`, tagged, and then pinned uniformly across all four consumers.

### Adopted Design Recommendations
1. **Shared CLI & `.bak` importer code lives behind opt-in Cargo features on `rusty-conduit-engine` (not a 6th repository):**
   - Keep default `rusty-conduit-engine` builds free of CLI/file-watcher dependencies (`clap`, `notify`, `rlimit`), preserving lightweight library embedding.
   - Unconditionally derive `serde::Serialize` alongside `Deserialize` on `rusty_conduit_engine::routing` config types (`serde` is already a required dependency).
   - Add an opt-in `import` feature (`routing` + `serde_json` + `base64`, all already in the engine's dependency graph) hosting the single authoritative AirSwitch / ZeroOmega / SwitchyOmega `.bak` importer returning structured `RoutingInput` / profile / warning ASTs for both `rusty-conduit-switch` and `rusty-conduit-gui`.
   - Add an opt-in `cli-support` (and `test-support`) feature on `rusty-conduit-engine` (updating `rusty-conduit-engine/DOX.md` explicitly to allow `clap`/`toml`/`rlimit` *only* behind opt-in non-default features) to eliminate ~6,000 lines of triplicated CLI flags, preflight checks, `fdlimit`, signal handling, and integration-test fixtures without adding another repo to `repos.tsv`.
2. **Bounded passive upstream cooldown on failover chains (on by default, `0s` disables):**
   - `ProfileRegistry` tracks lightweight per-profile atomic failure timestamps (`last_failed_at`, `cooldown = 3s` default, configurable). When a primary target in a multi-target failover chain (`["vpn", "ssh", "direct"]`) fails with a dial/timeout error, subsequent connections during the cooldown window skip straight to the next target instead of stalling every connection for the full 10 s `connect_timeout`, while allowing one probe attempt once the window elapses. Single-target routes never skip. No sockets or DNS entries are cached.
3. **Retire the live v1 GUI runtime stack while keeping one-way v1 → v2 data migration:**
   - Preserve `migrate_v2.rs` / `migration.rs` so upgrading `v0.1.0` users automatically convert saved v1 sessions into v2 Proxies and Tunnels at startup.
   - Delete the parallel live v1 execution and editing stack (`SessionManager`, `runner.rs`, `controller/sessions.rs`, `SessionEditor.svelte`) before `rusty-conduit-gui` `v0.2.0` stable, eliminating 2–4× duplication of SSH supervision, host-key probing, and vault auth resolution.

---

## 2. Correctness, Security & Drift Bugs (`B-01` – `B-12`)

These defects were uncovered during the cross-series code audit and should be fixed early (Phase 1 & Phase 2).

| ID | Severity | Repo / Component | Defect & Root Cause | Fix |
| :--- | :--- | :--- | :--- | :--- |
| **B-01** | **High** | `rusty-conduit-engine` `src/http/mitm_tunnel.rs:621-634` | **`MitmInterceptor::should_bypass` skips domain normalization.** `FilterRule::matches_domain` (`src/filter.rs:78-88`) requires lowercase input with trailing `.` stripped, but `should_bypass` only strips `[]` brackets. `CONNECT Example.com:443` or `CONNECT example.com.:443` fails to match `--mitm-bypass-host` and is MITM-intercepted. | Normalize `trimmed` via shared `normalize_domain` before calling `matches_domain` (matching `HostFilter::check_host` and `SelectiveServerCertVerifier`). |
| **B-02** | **High** | `rusty-conduit-gui` `crates/conduit-vault/src/crypto.rs:127-134, 185-190`, `src/keys.rs:433-448` | **Unbounded Argon2id cost parameters in `vault.bin` and `"CVBK"` backups.** While `src-tauri/src/controller/export.rs:623-635` caps `EncryptedExport` KDF params (`<= 1 GiB`, `t <= 64`, `p <= 16`), `VaultHeader::unwrap_dek` and `conduit_vault::import_backup` pass unauthenticated `Argon2Params` (`memory_kib` up to `u32::MAX` = 4 TiB) straight to `WorkMemory::new`, enabling memory/CPU DoS before AEAD authentication runs. | Enforce `MAX_ARGON_MEMORY_KIB`, `MAX_ARGON_TIME_COST`, and `MAX_ARGON_PARALLELISM` centrally inside `Argon2Params::to_argon2()`. Also wrap raw DEK byte copies (`Dek::to_bytes`, `unwrap_dek`, `keyring.rs`, `generate_key` seeds) in `Zeroizing` and set `0o600` via `OpenOptionsExt::mode` *before* writing temp files in `store.rs` and `conduit-core/src/storage.rs`. |
| **B-03** | **High** | `rusty-conduit-ssh` `src/ssh.rs:467-474`; `rusty-conduit-gui` `crates/conduit-openssh/src/{orphan,supervisor,agent_server,runtime_dir}.rs` | **Orphan `ssh` subprocesses & Windows IPC ACL gaps.** (1) `rusty-conduit-ssh` uses only userspace `kill_on_drop(true)`: on `SIGKILL`/OOM, `ssh -N -D -R` stays alive under PID 1 and holds remote `-R` ports forever, causing restarted instances to fail `ExitOnForwardFailure=yes`. (2) `conduit-openssh` has no parent-death watchdog for top-level `ssh` on macOS (yet spawns an idle `"conduit-ssh-parent"` OS thread on macOS/Windows), lacks a startup sweep of crashed `/tmp/rc-*` dirs, fails if `OpenSshSupervisor::start` is called with `socks_port == 0` (`supervisor.rs:315-316`), and creates Windows `IsolatedAgentServer` named pipes (`agent_server.rs:149-153`) with default `NULL` `SECURITY_ATTRIBUTES` instead of an owner-only SID DACL. | Add Linux `PR_SET_PDEATHSIG(SIGTERM)` + Windows Job Object + macOS parent-pipe/kqueue watchdog (`conduit-worker` wrapper or stdin EOF monitor); gate `"conduit-ssh-parent"` thread to `#[cfg(target_os = "linux")]`; apply owner-only Windows DACLs on agent pipes and runtime dirs; sweep stale `rc-*` dirs at startup; capture `.local_addr()?.port()` when `socks_port == 0`. |
| **B-04** | **High** | `rusty-conduit-gui` `crates/conduit-core/src/toml_io.rs:156-201, 272-293, 395-434, 1001-1013, 1335-1416`, `crates/conduit-runtime/src/toml_watcher.rs:154-165` | **CLI `config.toml` import/export drift & broken v2 `@tunnel:` export.** (1) `ConduitFile`, `SshFile`, and `SwitchFile` use `#[serde(deny_unknown_fields)]` but omit `error_page`, rejecting valid CLI configs. (2) After `migrate_tunnel_profiles` (`v2_model.rs:700-732`) replaced `UpstreamKind::Tunnel` with `@tunnel:<uuid>` and `@forward:<tid>:<fid>` routing targets, `export_rusty_conduit_ssh_toml` rejects `@tunnel:` proxies and `export_rusty_conduit_switch_toml` emits raw `@tunnel:<uuid>` targets with no `[profiles.*]` table. (3) `merge_external_toml` silently drops `socks_block_web`. | Add `error_page` to CLI TOML schemas; resolve `@tunnel:<uuid>` and `@forward:<tid>:<fid>` in both SSH and Switch TOML exporters (and run `migrate_tunnel_profiles` inside `commit_toml_import`); copy `socks_block_web` in `merge_external_toml`. |
| **B-05** | **High** | `rusty-conduit-gui` `src-tauri/ui/src/lib/{types.ts,stores.svelte.ts,mock.ts}`, `components/{CaVaultSection,JumpChainBuilder}.svelte` | **Incomplete v1 → v2 UI migration bugs & drifted TS types.** (1) `CaVaultSection.svelte:23-30, 169-185` and `store.deleteMitmCa` (`stores.svelte.ts:552-567`) inspect only `usage.sessions`, ignoring `usage.proxies` — force-stopping running v2 Proxies without warning (`deleteKey` similarly ignores `usage.tunnels`). (2) `store.testTunnelChain` (`stores.svelte.ts:1449-1459`) never sets `store.testHostKey`, so `HostKeyModal` never opens on unknown host keys. (3) `newProxyFromPreset` (`stores.svelte.ts:1139-1154`) still emits deprecated `UpstreamKind::Tunnel` profiles instead of `@tunnel:<id>`. (4) `types.ts:13-27, 395` omits `"proxy"` and `"tunnel"` from `AppErrorCode` and `PortConflictKind`. | Update CA/key usage modals and delete guards to union `proxies`, `tunnels`, and drafts; wire `store.testHostKey` in `testTunnelChain`; emit `@tunnel:<id>` in `newProxyFromPreset`; sync `types.ts` and `mock.ts`. |
| **B-06** | **High** | `rusty-conduit-engine` `src/server.rs:533-543, 638-639`, `src/http/mod.rs:220-229`, `src/http/mitm_tunnel.rs:1178-1180` | **Slowloris HTTP permit exhaustion, unbounded H2 streams, and leaked tasks after `drain_timeout`.** (1) Dedicated HTTP ports set no header-read timeout (`1,024` silent connections exhaust `max_connections`). (2) MITM `server_http2::Builder` leaves `max_concurrent_streams` unbounded (1 client permit can trigger thousands of outbound streams/dials when downgraded). (3) `TaskTracker::wait()` does not abort tasks when `drain_timeout` expires, leaving stuck tasks alive in `rusty-conduit-gui`. | Add header-read / half-close timeouts on HTTP/1.1, set `.max_concurrent_streams(256)` on MITM H2, and track connection tasks in a `JoinSet` (or cancel inner dial/hyper futures via `conn.shutdown`) so `drain_timeout` aborts remaining tasks. |
| **B-07** | **Medium** | `rusty-conduit-switch` `src/reload.rs:256-270`, `rusty-conduit-engine` `src/routing.rs:781-817` | **Hot-reload `RoutingCounters` leak & unnamed-rule counter collision.** `reload_once` carries `Arc<RoutingCounters>` across reloads without pruning removed profiles/rules, and unnamed rules use positional keys (`"[routing] rule #1"`), inheriting unrelated byte/hit totals when rules are inserted or reordered. | Prune stale keys on reload and key unnamed rules by a content hash or reset unnamed positional counters when rule order changes. |
| **B-08** | **Medium** | `rusty-conduit-switch` `src/import/mod.rs:88-169`, `src/import/airswitch.rs:318-341, 971-1000` | **AirSwitch TOML serializer & macros drifted from engine types.** Hand-rolled `render_profile` omits `tls_insecure_skip_verify`, `rule_lines` omits `bypass_mitm`, `all_none!`/`pick!` macros omit `bypass_mitm`, and `merge()` fails (`None`) whenever outer and inner nested `SwitchProfile` rules both set `host_wildcard`. | Enforce exhaustive struct destructuring in importer/renderer, emit `tls_insecure_skip_verify` and `bypass_mitm`, and conjoin overlapping condition fields where representable. |
| **B-09** | **Medium** | `rusty-conduit-ssh` `src/lib.rs:107-110`; `rusty-conduit-switch` `src/lib.rs:62-65`; `tests/cli_contract.rs` | **Startup version banner & CLI contract drift.** `-ssh` and `-switch` log `env!("CARGO_PKG_VERSION")` instead of `config::app_version()`, dropping `-dev` and `-beta` suffixes. `SHARED_FLAGS` in all 3 `cli_contract.rs` files omits `--mitm-insecure-host`, `--mitm-bypass-host`, `--mitm-insecure`, and `--error-page`, allowing `--mitm-bypass-host` help text to diverge. | Use `config::app_version()` in all startup banners and move `SHARED_FLAGS` / shared clap args to shared CLI support. |
| **B-10** | **Medium** | `rusty-conduit-ssh` & `rusty-conduit-switch` `.github/workflows/release.yml:79-97` | **Missing tag-vs-`Cargo.toml` version guard in 2 of 3 CLI release workflows.** Only `rusty-conduit/.github/workflows/release.yml:80-90` aborts when a `vX.Y.Z` tag disagrees with `Cargo.toml`. | Unify CLI `release.yml` workflows and enforce the tag-vs-`Cargo.toml` check everywhere. |
| **B-11** | **Medium** | `rusty-conduit-ssh` `src/ssh.rs:450-457, 502-548`, `src/lib.rs:288-300` | **Ephemeral `-D` port TOCTOU & `-R` startup readiness race.** `pick_loopback_port` closes the ephemeral socket before `ssh` binds it (allowing another local SOCKS5 instance to answer `probe_socks5` during `ssh` handshake), and `-D` becomes ready before remote `sshd` rejects `-R` `tcpip-forward`. | Verify child liveness + unique probe or `-W`/stdio readiness (`ExitOnForwardFailure=yes` + brief post-ready liveness check when `-R` forwards are configured). |
| **B-12** | **Low** | Workspace `README.md:82`; `examples/homelab-stack/compose.yaml:90`; `examples/smoke-test.sh:47-55` | **Workspace doc & smoke-test minor bugs.** `README.md:82` says `"Five runnable Compose projects"` instead of `"Six"`; `homelab-stack/compose.yaml:90` uses unpinned `traefik/whoami:latest`; `smoke-test.sh` `wait_pool` returns `0` on timeout and checks `switch_http`/`egress_pool` without awaiting them. | Update `README.md:82` (`Six`), pin `traefik/whoami`, make `wait_pool` return `1` on timeout, and await all 3 pools in `homelab-stack`. |

---

## 3. Performance & Scalability Optimizations (`P-01` – `P-15`)

### 3.1 Binary Builds & Linux Memory Footprint (Cross-Series)
- **`P-01` (High) — Add `[profile.release]` across all 4 binary repositories:**
  - *Files:* `rusty-conduit/Cargo.toml`, `rusty-conduit-ssh/Cargo.toml`, `rusty-conduit-switch/Cargo.toml`, `rusty-conduit-gui/Cargo.toml`.
  - *Problem:* None of the binary `Cargo.toml`s define `[profile.release]`. Release builds compile with `lto = false`, `codegen-units = 16`, and `strip = false`, preventing cross-crate inlining across the `rusty-conduit-engine` boundary and inflating release binaries/images by ~30–50%. Additionally, `rusty-conduit-gui/Cargo.toml:50-51` sets `[profile.dev] opt-level = 0` without optimizing crypto crates, making `128 MiB` Argon2id vault unlock slow in dev builds.
  - *Action:* Add `lto = "thin"`, `codegen-units = 1`, and `strip = "symbols"` to `[profile.release]` in all 4 repos, plus `[profile.dev.package."*"] opt-level = 2` in `rusty-conduit-gui/Cargo.toml`.
- **`P-02` (High) — Cap glibc malloc arenas automatically on Linux (`8.5×` per-tunnel RAM savings):**
  - *Context:* Measured benchmarks in `PERFORMANCE-AND-SIZING.md` show 18-core Linux uses **~42 MB idle / ~220 KB per open tunnel** under default glibc arenas vs **~7 MB idle / ~26 KB per tunnel** with `MALLOC_ARENA_MAX=2` at identical throughput (2.2–2.7 GB/s). Currently only Dockerfiles set `ENV MALLOC_ARENA_MAX=2`; standalone Linux CLI binaries and Linux GUI `.deb`/`.rpm`/`.AppImage` packages still pay the 8.5× memory penalty unless users manually configure environment variables.
  - *Action:* On `#[cfg(all(target_os = "linux", target_env = "gnu"))]`, if `std::env::var_os("MALLOC_ARENA_MAX").is_none()`, call `unsafe { libc::mallopt(libc::M_ARENA_MAX, 2); }` at the start of `main` in all 3 CLIs and `rusty-conduit-gui`.

### 3.2 Shared Engine (`rusty-conduit-engine`)
- **`P-03` (High) — Set `TCP_NODELAY` on accepted client sockets (`src/server.rs:595-615`):**
  - Call `let _ = stream.set_nodelay(true);` right alongside `ka.apply(&stream)` in `accept_loop` to eliminate 40–200 ms Nagle + Delayed-ACK latency spikes on SOCKS5 handshakes, `200 Connection Established` + MITM `ServerHello`, HTTP/2 control/gRPC frames, and interactive tunnels.
- **`P-04` (High) — Async DNS resolution for `resolve_dns = true` routing rules (`src/router/condition.rs:178-187, 764-770`, `src/router/mod.rs:321`):**
  - Add `Router::needs_dns(inbound) -> bool`. When `true` and the target is a hostname, resolve IPs asynchronously via `tokio::net::lookup_host` (bounded by timeout) before calling `Router::route_with_ips`, eliminating blocking `to_socket_addrs()` calls on Tokio worker threads.
- **`P-05` (High) — Reuse `rustls::ServerConfig` session storage across MITM `CONNECT` tunnels (`src/http/mitm_tunnel.rs:763-778`):**
  - Construct a single shared `Arc<dyn rustls::server::StoresServerSessions>` (e.g., `ServerSessionMemoryCache::new(4096)`) and `Ticketer` on `MitmInterceptor` (or pre-build `ServerConfig`s with a per-connection SNI/task-local `ResolvesServerCert`), restoring TLS 1.2/1.3 client session resumption across parallel browser `CONNECT` tunnels and eliminating 32-shard session-cache allocations per connection. Pre-build fixed-ALPN `Arc<ClientConfig>` variants in `Dialer` (`mitm_tunnel.rs:483-485`) as well.
- **`P-06` (High) — Happy Eyeballs (RFC 8305) dual-stack dialing (`src/net.rs:140-145, 239-251`):**
  - Interleave resolved `AAAA` and `A` candidates and stagger the secondary address family by `250 ms` so a blackholed IPv6 route fails over to IPv4 in 250 ms rather than timing out the whole 10 s connection with `504`.
- **`P-07` (High) — Passive upstream cooldown in `ProfileRegistry` / `FailoverDialer` & single timer per attempt (`src/upstream/mod.rs:295-308, 535-650`):**
  - Track per-profile `AtomicU64` failure epoch-ms in `ProfileRegistry` so multi-target failover chains bypass a known-dead primary during a brief cooldown window (default `3s`) while letting one probe through after expiry. Remove outer redundant `with_timeout` wrappers and make timeout error context formatting lazy (`|| format!(...)`) so successful dials allocate zero error strings.
- **`P-08` (High) — Zero-allocation disabled logging, non-blocking `AccessGuard::drop`, and single-buffer log encoding (`src/logging.rs:180-209, 396-506`, `src/http/mod.rs:350-377, 459-460`):**
  - Replace `logger.debug(format!(...))` / `logger.verbose(format!(...))` with lazy formatting macros (`log_debug!(logger, "...")`) or `fmt::Arguments` closures checked *before* formatting.
  - Skip `HttpAccessRecord` / `SocksLogRecord` `String` allocations and `OffsetDateTime::now_utc()` syscalls when `!access.http_enabled()` / `!access.socks_enabled()`.
  - Use `mpsc::Sender::try_send` in `AccessGuard::drop` (spawning a fallback task only if the 4,096-slot queue is full), saving 1 `tokio::spawn` per HTTP request.
  - Encode logfmt/JSON lines directly into a pre-sized `String::with_capacity(256)` via `write!` instead of allocating intermediate `Vec<(&str, Value)>` and per-field `String`s (~14 fewer heap allocations per logged request).
- **`P-09` (Medium-High) — Index `Router` and `HostFilter` for `O(1)` domain/regex matching & cut per-route clones (`src/router/mod.rs:212-217, 327-434`, `src/router/condition.rs:484-615, 758-796`, `src/filter.rs:171-328`, `src/routing.rs:801-850, 929-931`):**
  - Compile `Condition::Host` and `HostFilter` exact domains into `HashSet<Box<str>>`, `*.domain` suffixes into a label-walking `HashSet`, multi-pattern `HostRegex`/`HostWildcard`/`UrlWildcard`/`UrlRegex`/`BypassList` into `regex::RegexSet`, `Keyword` into `aho-corasick` (or fast substring scan), and adjacent pure-host SwitchyOmega rules into a jump index so 5,000-rule imported configs route in microseconds rather than running 5,000 `Regex::is_match` calls.
  - Return `PinnedRouting(Arc<RoutingState>)` by value instead of `Arc::new(PinnedState(...))` (`1` fewer heap alloc per request), normalize hostnames once via `Cow<str>`, stop cloning `table.default` before checking rule matches, pre-attach `Arc<TrafficCounters>` to compiled rules/profiles (eliminating 2 `DashMap` lookups per request), and cache `LocalTime` (`weekday`, `minute_of_day`) in an `AtomicU64` keyed by `unix_secs / 60` to avoid `localtime_r`'s global mutex on time-based rules.
- **`P-10` (Medium) — Data-plane buffer sizing, vectored writes, H2 adaptive flow control, and O(1) `CertCache` eviction:**
  - Switch `relay_bidirectional` (`src/net.rs:265`) to `tokio::io::copy_bidirectional_with_sizes(client, upstream, 32 * 1024, 32 * 1024)` and pass `guarded_first_chunk`'s buffer forward in SOCKS (`src/socks/mod.rs:422-423`).
  - Forward `poll_write_vectored` and `is_write_vectored` in `UpstreamStream`, `CountingStream`, and `PrefixedStream`, and replace `PrefixedStream::poll_read`'s `initialize_unfilled()` + `Vec::drain` with a cursor (`src/net.rs:308-315`).
  - Enable `.adaptive_window(true)` on MITM HTTP/2 client and server builders (`src/http/mitm_tunnel.rs:1178-1195`), and check whether a `CONNECT` host can actually match a URL rule before forcing `per_request = true` (`mitm_tunnel.rs:709-722`) so one narrow URL rule doesn't disable HTTP/2 globally.
  - Replace `CertCache`'s sync-mutex `entries.retain` + `O(N)` `min_by_key` scan (`src/mitm/cache.rs:153-190`) with an `O(1)` LRU/FIFO ring or min-heap.

### 3.3 CLI Runtimes (`rusty-conduit-ssh` & `rusty-conduit-switch`)
- **`P-11` (Medium) — Deduplicate startup regex compilation & MITM CA loading:**
  - Return compiled `Router` from `Config::validate` in `rusty-conduit-switch` instead of compiling every regex **3×** at startup/`validate` and **2×** per hot reload (`src/lib.rs:56, 78, 111`, `src/reload.rs:305-306`).
  - Load `CaMaterial` + OS root `ClientConfig` once at startup in `rusty-conduit-ssh` instead of up to **3×** across `preflight_before_ssh`, `ReverseProxy::start`, and `serve` (`src/lib.rs:192, 276`, `src/reverse.rs:91`).
- **`P-12` (Medium) — Direct `libc::kill`, reconnect backoff jitter & brief reconnect hold in `rusty-conduit-ssh`:**
  - Replace `Command::new("kill")` in `request_terminate` (`src/ssh.rs:564-578`) with `libc::kill(pid as libc::pid_t, libc::SIGTERM)`, add ±20% jitter to `next_delay` (`src/ssh.rs:434-437`), and optionally wait briefly on `TunnelState::Ready` in `Socks5UpstreamDialer::connect` (`src/net.rs:57-78`) during transient reconnects.

### 3.4 Desktop GUI (`rusty-conduit-gui`)
- **`P-13` (High) — Cursor-based delta IPC (`since_seq`) & stable virtualization keys in `LogDrawer.svelte`:**
  - *Files:* `src-tauri/ui/src/lib/components/LogDrawer.svelte:142-246`, `crates/conduit-runtime/src/logs.rs:71-88, 213-279`, `crates/conduit-runtime/src/proxy_manager.rs:230-249, 699-700`, `src-tauri/src/controller/proxies.rs:50-116, 257-280`.
  - *Action:* Add monotonic `seq: u64` to `AccessRecordBuffer` and `since_seq: Option<u64>` to `get_proxy_logs`, `get_proxy_access_records`, and `get_tunnel_logs`; append deltas into bounded client-side ring buffers; key access rows by `` `a${record.seq}` `` instead of `` `a${record.ts_ms}:${index}` `` (fixing full-DOM thrashing and broken autoscroll at 2,000 records); remove the unused 512-slot `broadcast::Sender` in `LogRingBuffer`; and skip `to_ascii_lowercase()` in `redact()` when no secret delimiter/prefix byte can match.
- **`P-14` (High) — Event-driven `tray_bridge` & lightweight snapshot-only runtime polling:**
  - *Files:* `src-tauri/src/tray_bridge.rs:28, 71-125, 255`, `src-tauri/src/controller.rs:528-534`, `src-tauri/ui/src/lib/stores.svelte.ts:571-593`.
  - *Action:* Notify `tray_bridge` via a `tokio::sync::Notify` / `watch` channel on config, vault, or runtime transitions instead of cloning `AppConfig` 3× and calling `Path::exists()` every 2 s while idle; also fix `rule_count` (`tray_bridge.rs:95`) to include `[routing.http]` and `[routing.socks]` rules. Add `get_runtime_snapshots` returning `(VaultStatus, Vec<ProxySnapshot>, Vec<TunnelSnapshot>, config_revision: u64)` so `stores.svelte.ts`'s 2 s poll stops serializing multi-thousand-rule `Proxy` configs across IPC on every tick.
- **`P-15` (Medium) — Pre-resolved `TunnelForwardDialer`, bounded `NestedTransport`, and `RusshDialer` error typing:**
  - Pre-resolve immutable `(protocol, dest_host, dest_port, redacted_label)` in `TunnelForwardDialer` (`crates/conduit-runtime/src/forward_dialer.rs:76-120`) and cache `Socks5Dialer` in `OpenSshDialer` (`crates/conduit-openssh/src/dialer.rs:42`).
  - Add connect timeouts and connection semaphores to `crates/conduit-ssh/src/reverse.rs:162-190` and `crates/conduit-runtime/src/port_forward.rs:98-133`; replace `NestedTransport`'s `unbounded_channel<Vec<u8>>` + `buf.to_vec()` (`crates/conduit-ssh/src/nested.rs:64-72`) with a bounded `mpsc::channel<Bytes>`; and wrap disconnected `RusshDialer` errors in `DialError::NotConnected` (`crates/conduit-ssh/src/dialer.rs:88-91`).

---

## 4. Maintainability, Deduplication & CI/Build Optimizations (`M-01` – `M-06`)

- **`M-01` (High) — Consolidate ~6,000 LOC of triplicated CLI & test-harness code behind opt-in `rusty-conduit-engine` features:**
  - Move `fdlimit.rs` (3 × 107 LOC), `preflight.rs` (3 × 162 LOC), `shutdown_signal` (3 × 33 LOC), `app_version()`, 26 shared `clap` flags + TOML `[mitm]`/`[logging]`/`keepalive` merge & validation, `ReverseProxy` (`rusty-conduit-ssh/src/reverse.rs` + `conduit-runtime/src/reverse.rs`), and shared `TestCa` / echo / origin / SOCKS5 test fixtures into opt-in `cli-support` and `test-support` modules in `rusty-conduit-engine`. Delete `rusty-conduit-ssh/src/net.rs:115-226`'s duplicate SOCKS5 client framing in favor of `rusty_conduit_engine::upstream::socks5`. Align engine default constants (`DEFAULT_MAX_CONNECTIONS`, `DEFAULT_MITM_CERT_CACHE_MAX`) across engine, CLIs, and `conduit-core` (`10,000` → `10,240`), and add `#[non_exhaustive]` to public engine option structs at the next minor bump.
- **`M-02` (High) — Unify `.bak` importer, `Serialize` engine routing AST, and event-driven TOML watcher:**
  - Derive `Serialize` on `rusty_conduit_engine::routing` config types and delete the duplicated `RoutingRule` / `RoutingTable` AST & adapters in `conduit-core/src/{v2_model,v2_mapping}.rs`.
  - Extract `rusty-conduit-switch/src/import/` into `rusty-conduit-engine` (feature `import`) returning structured config + warnings so `conduit-core/src/airswitch_import.rs` (919 LOC) is replaced by a thin adapter with full `RuleListProfile`, `VirtualProfile`, nested `SwitchProfile`, and `RuleMatcher::compile` parity.
  - Replace `conduit-runtime/src/toml_watcher.rs`'s 250 ms sync-FS polling loop with `notify` (shared pattern with `rusty-conduit-switch/src/reload.rs`, extended to handle Kubernetes `..data` symlink updates and bounded max-wait debounce).
- **`M-03` (Medium-High) — Retire legacy v1 GUI runtime stack:**
  - Keep `crates/conduit-core/src/migrate_v2.rs` + `src-tauri/src/migration.rs` (plus migration unit tests) for seamless v0.1.0 → v0.2.0 startup data conversion, and remove `SessionManager` (`crates/conduit-runtime/src/{manager,runner}.rs`), `src-tauri/src/controller/sessions.rs`, and `SessionEditor.svelte`. Also complete the tracked `MitmConfig.socks_block_web` top-level field cleanup (`rusty-conduit-gui/docs/TODO.md`).
- **`M-04` (Medium-High) — Automate Rust ↔ TypeScript IPC contract (`specta` or schema test):**
  - Generate `src-tauri/ui/src/lib/bindings.ts` from `src-tauri` command/DTO types (via `specta` / `ts-rs`) or add a `cargo test` contract test asserting TypeScript union/struct parity so `types.ts` and `mock.ts` can never silently drift from `src-tauri`.
- **`M-05` (Medium) — CI & Release pipeline acceleration across GUI and CLIs:**
  - In `rusty-conduit-gui/.github/workflows/release.yml`: add `Swatinem/rust-cache@v2` and invoke `@tauri-apps/cli` from `node_modules` (or `taiki-e/install-action@cargo-tauri`) instead of compiling `tauri-cli` from source across 5 matrix runners (~30–50 CI minutes saved per release). Add `beforeDevCommand` / `beforeBuildCommand` to `src-tauri/tauri.conf.json`.
  - Across CLI repos: share reusable `ci.yml` / `release.yml` templates (enforcing `check-pure-rust-crypto.py`, `CARGO_NET_GIT_FETCH_WITH_CLI=true`, and the tag-vs-`Cargo.toml` version guard), add GHA BuildKit caching to `release.yml` Docker jobs, align `Dockerfile` builder/runtime base distros, pass `ARG CONDUIT_RELEASE_VERSION`, and use BuildKit cargo cache mounts so engine tag bumps don't rebuild 180 crates cold.
- **`M-06` (Low-Medium) — Workspace pin-check script & hermetic smoke-test ports:**
  - Add `scripts/check-workspace.py` (verifying all 4 consumer `Cargo.toml`s + GUI docs/workflows pin the same `rusty-conduit-engine` tag, verifying `python3 scripts/site-diagrams.py` leaves zero SVG diff, and checking relative markdown links; run in `.github/workflows/pages.yml`).
  - Parameterize host ports in `examples/*/compose.yaml` (`127.0.0.1:${RCS_HTTP_PORT:-3128}:3128`, etc.) so [smoke-test.sh](../examples/smoke-test.sh) can run without colliding with a developer's running local proxy.

---

## 5. Phased Execution Plan

> **Tip for future sessions:** Because this plan spans multiple independent git repositories and may run across sessions, execute it phase-by-phase (e.g., with `goal-ledger` or one phase per session). Always check `scripts/bootstrap.sh --check` before starting a phase, and commit each change in the repository that owns the modified files.

### Phase 1 — Quick High-ROI Wins, Build Profiles & Standalone Bug Fixes (No Engine Tag Required)
Can be executed immediately in each consumer repo and the workspace without waiting on an engine release:
1. **All 4 consumer repos (`rusty-conduit`, `rusty-conduit-ssh`, `rusty-conduit-switch`, `rusty-conduit-gui`):**
   - Add `[profile.release]` (`lto = "thin"`, `codegen-units = 1`, `strip = "symbols"`) (`P-01`).
   - Add `[profile.dev.package."*"] opt-level = 2` in `rusty-conduit-gui/Cargo.toml` (`P-01`).
   - Add startup `libc::mallopt(libc::M_ARENA_MAX, 2)` on `linux-gnu` when `MALLOC_ARENA_MAX` is unset (`P-02`).
2. **`rusty-conduit-gui` standalone security, correctness & CI fixes:**
   - Enforce Argon2 memory/time/parallelism upper bounds in `conduit-vault/src/crypto.rs` (`Argon2Params::to_argon2`), wrap raw DEK copies in `Zeroizing`, and create temp files with mode `0o600` up front (`B-02`).
   - Fix `toml_io.rs` (`error_page` field + `@tunnel:` / `@forward:` CLI export) and `toml_watcher.rs` (`socks_block_web`) (`B-04`).
   - Fix `CaVaultSection.svelte` / `deleteMitmCa` / `deleteKey` v2 usage checks, `testTunnelChain` `HostKeyModal` wiring, `newProxyFromPreset` `@tunnel:` targets, and `types.ts` union variants (`B-05`).
   - Update `.github/workflows/release.yml` (`Swatinem/rust-cache@v2` + prebuilt `tauri-cli`) and `tauri.conf.json` build hooks (`M-05`).
3. **`rusty-conduit-ssh` & `rusty-conduit-switch` standalone fixes:**
   - Fix startup banner `config::app_version()` in `-ssh` and `-switch` and add missing flags to `tests/cli_contract.rs` (`B-09`).
   - Restore tag-vs-`Cargo.toml` check + `check-pure-rust-crypto.py` + Docker BuildKit caching across CLI workflows/Dockerfiles (`B-10`, `M-05`).
   - Replace `/bin/kill` subprocess with `libc::kill`, add Linux `PR_SET_PDEATHSIG` + Windows Job Object + macOS orphan watchdog (in both `-ssh` and `conduit-openssh`, plus Windows pipe DACLs), and add reconnect jitter (`B-03`, `B-11`, `P-12`).
   - Fix `RoutingCounters` reload pruning/keys (`B-07`) and deduplicate startup/reload `Router` compilation (`P-11`).
4. **Workspace (`rusty-conduit-series`):**
   - Fix `README.md:82` (`Six runnable Compose projects`), `homelab-stack/compose.yaml` image pin, `examples/smoke-test.sh` `wait_pool` + port env vars, and add `scripts/check-workspace.py` (`B-12`, `M-06`).
- **Verification:** Run each touched repo's `DOX.md` Verification suite (`cargo fmt --check`, `cargo clippy --all-targets --locked -- -D warnings`, `cargo test --locked`, GUI `npm run check && npm test && npm run build`, `scripts/bootstrap.sh --check`).

---

### Phase 2 — Engine Core Performance, Resilience & Security Release (`rusty-conduit-engine` `v0.7.0`)
1. **Land in `rusty-conduit-engine` (with `docs/DIVERGENCE-LEDGER.md` entries and unit/integration tests):**
   - `B-01`: Normalize hostnames in `MitmInterceptor::should_bypass`.
   - `B-06`: Add HTTP/1.1 header-read / half-close timeouts, MITM H2 `.max_concurrent_streams(256)`, and task abort on `drain_timeout`.
   - `P-03`: Enable `TCP_NODELAY` on accepted client sockets in `accept_loop`.
   - `P-04`: Async DNS resolution via `tokio::net::lookup_host` before routing when `resolve_dns = true`.
   - `P-05`: Shared `StoresServerSessions` / `ServerConfig` reuse across MITM `CONNECT` tunnels + pre-built `ClientConfig` ALPN variants.
   - `P-06`: Happy Eyeballs (RFC 8305) dual-stack dialing in `src/net.rs`.
   - `P-07`: Bounded passive failure cooldown in `ProfileRegistry` / `FailoverDialer` + lazy timeout error formatting + single timer per attempt.
   - `P-08`: Lazy `Logger` macros, fast-path `AccessGuard::drop` (`try_send`), skip disabled `AccessRecord` allocs, single-buffer logfmt/JSON formatting.
   - `P-10`: `32 KiB` `copy_bidirectional_with_sizes`, `poll_write_vectored` forwarding, `PrefixedStream` cursor, MITM H2 `.adaptive_window(true)` + scoped `per_request` URL-rule check, and `O(1)` `CertCache` eviction.
2. **Verification:** Full engine CI matrix (`cargo fmt --check`, clippy + tests with default features and `--no-default-features`, `python3 scripts/check-pure-rust-crypto.py`).

---

### Phase 3 — Engine Router Indexing, `Serialize`, Shared Importer & CLI Support (`rusty-conduit-engine` → Consumers)
*(Can be combined into the same `v0.7.0` tag as Phase 2 before bumping consumers, so consumers only bump once.)*
1. **In `rusty-conduit-engine`:**
   - `P-09`: Index `Router` & `HostFilter` (`HashSet` exact domains, suffix-label `HashSet`, `RegexSet`, CIDR prefix lookup), by-value `PinnedRouting`, `Cow<str>` single normalization, pre-attached `Arc<TrafficCounters>`, and 1-minute atomic `LocalTime` cache.
   - `M-02`: Derive `Serialize` on `routing` config structs; add opt-in `import` feature with the unified AirSwitch / SwitchyOmega `.bak` importer (fixing `B-08` `tls_insecure_skip_verify`, `bypass_mitm`, and nested condition merging).
   - `M-01`: Update `rusty-conduit-engine/DOX.md` to permit `clap`/`toml`/`rlimit` strictly behind opt-in `cli-support` / `test-support` features; extract shared CLI args, TOML `[mitm]`/`[logging]`/`keepalive` merge, `fdlimit`, `preflight`, `shutdown_signal`, `ReverseProxy`, and shared test fixtures.
   - Cut annotated engine tag (`v0.7.0`) after full verification (`--no-default-features`, default features, `--all-features`).
2. **Bump & deduplicate all 4 consumers (`rusty-conduit`, `rusty-conduit-ssh`, `rusty-conduit-switch`, `rusty-conduit-gui`):**
   - Bump `rusty-conduit-engine` tag to `v0.7.0` across all 4 repos and GUI docs/workflows.
   - Replace triplicated CLI/preflight/fdlimit/test code in the 3 CLIs and delete duplicate SOCKS5 client code in `rusty-conduit-ssh/src/net.rs` + duplicate MITM CA loads (`P-11`).
   - Replace `conduit-core/src/{v2_model,v2_mapping}.rs` duplicate routing AST structs and `conduit-core/src/airswitch_import.rs` with `rusty-conduit-engine`'s `Serialize` types and `import` feature, and switch `conduit-runtime/src/toml_watcher.rs` to `notify` (`M-02`).

---

### Phase 4 — Desktop GUI Runtime & IPC Overhaul (`rusty-conduit-gui`)
1. **IPC & Polling (`P-13`, `P-14`, `P-15`):**
   - Implement `seq: u64` + `since_seq` delta fetching for logs and access records, key `LogDrawer.svelte` rows by `a${record.seq}`, remove unused `LogRingBuffer` broadcast channel, and fast-path `redact()`.
   - Make `tray_bridge.rs` event-driven (eliminating 2 s 3× `AppConfig` clones + `stat` syscalls) and add `get_runtime_snapshots` for `stores.svelte.ts`'s 2 s counter refresh.
   - Pre-resolve `TunnelForwardDialer`, bound `conduit-ssh` reverse/port-forward concurrency + timeouts, switch `NestedTransport` to bounded `Bytes`, and fix `RusshDialer` `DialError::NotConnected`.
2. **v1 Retirement & Typegen (`M-03`, `M-04`):**
   - Retire live v1 `SessionManager`, `runner.rs`, `controller/sessions.rs`, and `SessionEditor.svelte` (keeping startup `migrate_v2.rs` / `migration.rs`), unify `MitmConfig.socks_block_web` onto top-level `socks_block_web`, and add Rust → TypeScript IPC type generation / contract tests.
3. **Verification:** Full `rusty-conduit-gui` CI gate (`cargo clippy --workspace --all-targets -- -D warnings`, `cargo test --workspace`, `secret_leak_scan`, `check-pure-rust-crypto.py`, `validate-release-config.py`, `npm run check && npm test && npm run build`).
