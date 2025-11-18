# Bedrock AgentCore Starter Toolkit – Agent Handbook

This repository ships the `agentcore` CLI that helps developers configure, scaffold, and deploy agent runtimes onto Amazon Bedrock AgentCore. Use this guide to understand the surface area quickly and decide where to add or debug logic—including the new `agentcore create` workflow.

---

## Quick Orientation
- **CLI entry point** – `agentcore` is a [Typer](https://typer.tiangolo.com/) app that wires runtime, gateway, import, and create subcommands into one binary (`src/bedrock_agentcore_starter_toolkit/cli/cli.py:1`). Logging is centralized through `setup_toolkit_logging`.
- **Configuration** – All commands read/write `.bedrock_agentcore.yaml`, a multi-agent config modeled by `BedrockAgentCoreAgentSchema` and `BedrockAgentCoreConfigSchema` (`src/bedrock_agentcore_starter_toolkit/utils/runtime/schema.py:204` and `:257`). Treat this file as the single source of truth for agent metadata, AWS resources, and deployment state.
- **Operations layer** – `operations/runtime/*` host the procedural logic for configure/launch/invoke/destroy/status/stop-session and are thin wrappers over the AWS service-layer clients in `src/bedrock_agentcore_starter_toolkit/services`. Runtime interactions go through `BedrockAgentCoreClient` (`services/runtime.py:127`), while CodeBuild/ECR helpers live under `services/codebuild.py:20` and `services/ecr.py:1`.
- **Create feature** – The new `agentcore create` command guides users through SDK/IaC selection (`cli/create/commands.py:61`) and delegates to the templated generator in `create/generate.py:22`. Generation is driven by a `ProjectContext` (`create/types.py:21`) and a stack of `Feature` subclasses that render Jinja templates per provider (`create/features/base_feature.py:15`).
- **Testing** – Unit tests are under `tests/` (e.g., `tests/create/test_project_context.py:1`), with integration suites in `tests_integ/`. Use `pytest` for fast feedback and prefer snapshot tests for templated output.

---

## Command Surface

### Top-level commands
- `agentcore configure …` populates `.bedrock_agentcore.yaml` interactively or via flags, delegating to `configure_impl` and stateful helpers (`src/bedrock_agentcore_starter_toolkit/cli/runtime/commands.py:102`).
- `agentcore launch` compiles code (direct zip or Docker), builds via CodeBuild/local runtime, then deploys/upgrades the runtime (`cli/runtime/commands.py:211` → `operations/runtime/launch.py:1`).
- `agentcore invoke`, `status`, `destroy`, and `stop-session` call their counterparts in `operations/runtime/*`.
- `agentcore dev` starts a uvicorn-powered hot-reload server for the configured entrypoint (`cli/runtime/dev_command.py:24`).
- `agentcore gateway …` exposes helper commands for managed MCP Gateways (`cli/gateway/commands.py:15`).
- `agentcore import-agent` converts legacy Bedrock Agents into LangChain or Strands apps wired with AgentCore primitives (`cli/import_agent/commands.py:104`).

### The `agentcore create` flow
1. **Prompting & validation** – Run `agentcore create` inside an empty directory. The CLI enforces ARN-safe project names, optionally accepts `--init` for runtime-only scaffolding, and falls back to interactive SDK/model/IaC prompts (`cli/create/commands.py:61`–`:173`). Prompt UX is managed in `cli/create/prompt_util.py:12` and `cli/cli_ui.py`.
2. **Context building** – `generate_project` seeds a `ProjectContext` with defaults, selecting `TemplateDirSelection.MONOREPO` when IaC is requested or `RUNTIME_ONLY` otherwise (`create/generate.py:37`–`:77`). The context captures entrypoints, dependencies, AWS knobs (memory, VPC, custom auth), and derived metadata like `.env` variable names.
3. **Template execution** – `BaselineFeature` renders shared files (pyproject, README, lambda entrypoints) and injects default dependencies per template directory (`create/baseline_feature.py:16`). SDK-specific features are resolved via `sdk_feature_registry` (`create/features/__init__.py:17`), and each subclass renders `src/` content for its provider. IaC features (`CDKFeature`, `TerraformFeature`) are resolved through `iac_feature_registry` (`create/features/__init__.py:26`).
4. **Monorepo extras** – When a user has already run `agentcore configure`, `resolve_agent_config_with_project_context` copies their settings (protocol, memory, authorizers, network) onto the ProjectContext so the generated IaC mirrors reality (`create/configure/resolve.py:21`). The routine can also copy the user’s existing runtime code and Docker artifacts into the new monorepo (`create/configure/resolve.py:93`).
5. **Outputs** – Runtime-only projects get a minimal `.bedrock_agentcore.yaml` plus optional `.env` for API keys (`create/util/create_agentcore_yaml.py:45` and `create/util/dotenv.py:4`). IaC projects receive a `cdk/` or `terraform/` directory plus Dockerfile via `ContainerRuntime.generate_dockerfile` (`create/generate.py:155`). Completion banners summarize next steps (`create/util/console_print.py`).

Key invariants:
- Monorepo generation currently supports **Bedrock** model provider only; non-Bedrock providers are restricted to runtime-only flows (`create/generate.py:131`–`:138`).
- API keys for OpenAI/Anthropic/Gemini are collected interactively and written to `.env` so they never transit the template context (`create/util/dotenv.py:4`–`:20`).
- `.bedrock_agentcore.yaml` files emitted by create set `is_agentcore_create_with_iac` to signal downstream commands that they must call `resolve_create_with_iac_project_config` to discover Agent IDs post-deployment (`utils/runtime/create.py:10`).

---

## Configuration & Data Model
- `BedrockAgentCoreAgentSchema` covers entrypoints, deployment type, AWS metadata, CodeBuild info, authorizers, and optional API key provider bindings (`utils/runtime/schema.py:204`). `validate()` ensures required AWS/account fields exist unless running locally.
- `BedrockAgentCoreConfigSchema` wraps multiple agents, a `default_agent`, and the `is_agentcore_create_with_iac` flag. `get_agent_config()` enforces explicit selection for multi-agent projects (`utils/runtime/schema.py:257`).
- `load_config` auto-upgrades legacy single-agent YAMLs, fills in AWS account/region from the caller, migrates deployment types, and surfaces pydantic errors in friendly form (`utils/runtime/config.py:72`–`:145`).
- Runtime CLI commands should always go through `load_config`/`save_config` helpers to retain compatibility and automatic migrations; avoid manipulating YAML manually.

---

## Runtime Lifecycle Internals
1. **Configure** (`agentcore configure`)  
   - Detects entrypoints/requirements, infers a default agent name, and prompts for IAM roles/ECR/S3, OAuth settings, VPC topology, lifecycle limits, and memory settings via `ConfigurationManager` (`cli/runtime/configuration_manager.py:19`).  
   - Computes Dockerfiles through `ContainerRuntime` when container deployments are chosen (`utils/runtime/container.py:21`).  
   - Saves everything back to `.bedrock_agentcore.yaml` and caches Docker artifacts in `.bedrock_agentcore/<agent>/`.

2. **Launch** (`agentcore launch`)  
   - Parses CLI flags to decide between cloud (CodeBuild), local, or local-build modes (`cli/runtime/commands.py:211`).  
   - Validates mutually exclusive flags, ensures IaC projects are deployed through their IaC provider, and translates `--env` pairs into runtime environment variables.  
   - For container builds it provisions ECR repositories (`services/ecr.py:1`) and CodeBuild projects (`services/codebuild.py:20`), or falls back to local Docker/Finch/Podman when `--local`/`--local-build` is set.  
   - Direct-code deployments zip dependencies using `CodeZipPackager` (`utils/runtime/package.py:1`).  
   - After deployment, `BedrockAgentCoreClient` polls runtime/endpoint readiness and updates `.bedrock_agentcore.yaml` with the runtime ARN/ID.

3. **Invoke** (`agentcore invoke`)  
   - Marshals payloads, session IDs, and user tokens, then routes to either the AWS SDK (`BedrockAgentCoreClient.invoke_endpoint`) or the HTTP/mcp clients (`services/runtime.py:404+`).  
   - Local dev invocations first fetch a workload access token from AgentCore Identity and update OAuth callback URLs so 3LO flows succeed (`operations/runtime/invoke.py:1`).

4. **Dev Server** (`agentcore dev`)  
   - Reads `.bedrock_agentcore.yaml`, converts file paths to module paths, and launches `uv run uvicorn … --reload` with hot reload, injecting `LOCAL_DEV=1`, `PORT`, and `PYTHONPATH` automatically (`cli/runtime/dev_command.py:24`–`:180`).

5. **Status / Destroy / Stop-session**  
   - `agentcore status` enriches config info with live runtime and memory details, including VPC context and observability settings (`operations/runtime/status.py:1`).  
   - `destroy` and `stop-session` live in the same module and orchestrate runtime teardown while warning about leftover resources.

---

## AWS Service Integrations
- **Runtime control/data planes** – `BedrockAgentCoreClient` configures botocore clients with custom user agents, handles create/update flows for both container and direct_code_deploy runtimes, and wraps invoke/status/list APIs (`services/runtime.py:127`–`:401`). Helper classes (`HttpBedrockAgentCoreClient`, `LocalBedrockAgentCoreClient`) share serialization and event-stream parsing logic.
- **CodeBuild** – `CodeBuildService` creates per-agent build projects, ensures S3 source buckets exist (with lifecycle policies), zips sources honoring `.dockerignore`, and streams build logs (`services/codebuild.py:20`–`:210`). It relies on shared IAM role creation logic in `operations/runtime/create_role.py`.
- **ECR** – `sanitize_ecr_repo_name`, `get_or_create_ecr_repository`, and `deploy_to_ecr` normalize names, lazily provision repos, and tag/push images through the detected container runtime (`services/ecr.py:1`–`:74`).
- **Memory** – `operations/memory` provides the rich `MemoryManager` client plus typed strategy models. Use it when enabling memory from CLI or IaC and review the in-repo guide for advanced use (`src/bedrock_agentcore_starter_toolkit/operations/memory/README.md:1`).
- **Gateway** – `GatewayClient` handles MCP Gateway creation, IAM roles, authorizer wiring, and target registration (Lambda, Smithy, OpenAPI) (`operations/gateway/client.py:23`). Its CLI facade lives at `cli/gateway/commands.py:15`.
- **Identity/OAuth** – OAuth helpers spin up a localhost callback server for 3-legged flows and manage workload identities in `.bedrock_agentcore.yaml` (`operations/identity/oauth2_callback_server.py` referenced via `operations/runtime/invoke.py:1`).

---

## Templates & Code Generation
- Templates live under `create/templates/<variant>` for baseline assets and under `create/features/<provider>/templates` for SDK/IaC-specific files. All templates use `.j2` Jinja syntax and receive the serialized `ProjectContext`.
- `Feature.render_dir` first renders shared `common/` templates when `render_common_dir=True` (e.g., CDK) before materializing provider-specific files (`create/features/base_feature.py:70`–`:87`).
- Provider metadata, prompt descriptions, and allowed combinations are centralized in `create/constants.py:8`–`:84`. Update these when introducing new SDKs, IaC engines, or model providers.
- To support a new SDK:
  1. Add its literal to `CreateSDKProvider` and `ModelProvider` if needed (`create/types.py:7`, `create/constants.py:53`).
  2. Implement a `Feature` subclass that sets `feature_dir_name`, optional dependencies, and any `before_apply` logic (see `create/features/langgraph/feature.py`).
  3. Register it in `sdk_feature_registry` (`create/features/__init__.py:17`) and add templates under `create/features/<sdk>/templates/<template_dir_selection>/<model_provider?>/`.
  4. Expand tests/snapshots under `tests/create/features`.

---

## Working With `.bedrock_agentcore.yaml`
- `write_minimal_create_runtime_yaml` and `write_minimal_create_with_iac_project_yaml` encode the smallest viable config for projects generated by `agentcore create` (`create/util/create_agentcore_yaml.py:15`–`:57`).
- IaC-generated projects must call `resolve_create_with_iac_project_config` after deploying to populate runtime ARNs/IDs discovered via `list_agent_runtimes` (`utils/runtime/create.py:10`–`:55`).
- Runtime commands treat `.bedrock_agentcore.yaml` as canonical. Never mutate AWS identifiers elsewhere; always read/save through `utils/runtime/config.py`.

---

## Testing & Validation
- **Unit tests** live under `tests/` and mostly target pure Python modules (CLI helpers, generator utilities, container tooling). Example: `tests/create/test_project_context.py:1` ensures the dataclass serializes as expected.
- **Snapshot/template tests** reside in `tests/create/__snapshots__` and should be updated when templates change. Use `pytest --snapshot-update` (Syrupy) when intentionally changing scaffolding.
- **Integration tests** inside `tests_integ/` cover CLI flows against mocked services or real AWS accounts. These are slower and often gated via markers/environment variables.
- Before shipping changes:
  1. Run `pytest tests/create` to validate generator logic.
  2. Run targeted CLI tests (e.g., `pytest tests/cli`) if you touched interaction code.
  3. Lint via `ruff`/`mypy` (configured in `pyproject.toml:1`) and optionally `uv pip install -e .` to test the CLI end-to-end.
  4. Manually execute `agentcore create --init` and/or `agentcore create` to validate prompt flows plus `agentcore launch` in a sandbox AWS account.

---

## Extending & Debugging Tips
1. **Adding new create options** – Update literals in `create/types.py:7`–`:19`, selection prompts (`cli/create/prompt_util.py:34`), and registries (`create/features/__init__.py:17`). The CLI automatically validates CLI flags against these Literal types.
2. **Customizing prompts** – All interactive UI flows (welcome screen, text inputs, selectors) are defined in `cli/cli_ui.py`. Reuse these helpers to maintain UX consistency.
3. **Handling existing configs** – When bridging configure ↔ create, use `resolve_agent_config_with_project_context` to map YAML state into templating flags instead of re-reading YAML fields manually (`create/configure/resolve.py:21`).
4. **Credentials & secrets** – Non-Bedrock model providers require API keys; `ask_text_required` enforces non-empty input and `_write_env_file_directly` keeps secrets out of the rendered templates (`cli/create/prompt_util.py:25`, `create/util/dotenv.py:4`).
5. **AWS operations** – Keep AWS mutations in `operations/*` (business logic) or `services/*` (thin AWS clients). CLI layers should only parse arguments, run validations, and display results.
6. **Docs & releases** – MkDocs documentation lives under `documentation/` with `mkdocs.yaml` and supporting macros. Release automation scripts (`scripts/bump-version.py`, `scripts/prepare-release.py`) expect `pyproject.toml` to be canonical for versioning.

---

## Useful Local Workflows
- **Install & iterate**  
  ```bash
  uv pip install -e .
  agentcore --help
  ```
- **Scaffold a runtime-only sample**  
  ```bash
  agentcore create --project-name sample-runtime --init --sdk Strands --model-provider OpenAI --provider-api-key sk-***
  cd sample-runtime
  agentcore dev
  ```
- **Scaffold a monorepo**  
  ```bash
  agentcore configure --entrypoint src/main.py  # single-agent, container deployment
  agentcore create --project-name sample-mono --sdk LangGraph --iac CDK
  cd sample-mono/cdk && npm install && npm run cdk:deploy
  ```
- **Verify runtime pipeline**  
  ```bash
  agentcore configure --entrypoint src/main.py
  agentcore launch
  agentcore status
  agentcore invoke '{"prompt": "Hello"}'
  ```
- **Run tests**  
  ```bash
  pytest tests/create -q
  pytest tests/cli -q
  ```

Keep this file close while extending `agentcore create`: it summarizes the orchestration layers, invariants, and testing hooks so you can focus on your feature rather than rediscovering the architecture.
