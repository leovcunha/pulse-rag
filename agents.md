# Developer & Agent Guidelines (Repository Contract)

This document establishes the strict rules of engagement, code design principles, and operational guidelines for all AI agents and contributors working in this repository. Any code modifications or planning must adhere to this contract.

---

## 1. Think and Align Before Coding
*Do not assume user intent, do not hide technical uncertainty, and always make tradeoffs explicit before writing code.*

* **Explicit Assumptions**: If a requirement is underspecified or ambiguous, stop and state your assumptions before proceeding. If you are uncertain about a design decision, ask for clarification.
* **No Speculative Mocking/Fallbacks**: Never write speculative code, placeholder modes, or mock logic (e.g., simulating API responses because of missing keys) based on assumptions about user resources or configurations. If a resource or key is missing, halt and ask the user how they wish to proceed.
* **Surface Tradeoffs**: When multiple implementation paths exist, present them to the user with their pros, cons, and performance implications (e.g., latency, dependency overhead).
* **Propose Simpler Alternatives**: If a requested feature can be achieved through a simpler or more elegant design, propose it before implementing the more complex requested approach.
* **Halt on Confusion**: If you encounter contradictory requirements or confusing legacy code, stop immediately. Document the exact conflict and wait for clarification.

---

## 2. Radical Simplicity (YAGNI & KISS)
*Write the absolute minimum amount of code necessary to solve the problem. Do not write speculative code or build premature abstractions.*

* **No Speculative Features**: Only implement features explicitly requested. Do not add hooks, configurations, or helper methods for "future extension."
* **Compress and Rewrite**: Keep code compact and readable. If a solution can be implemented cleanly in 50 lines of simple, procedural code, do not write 200 lines of highly abstracted object-oriented code.
* **Realistic Error Handling**: Implement error handling for expected external failure modes (e.g., API timeouts, rate limits, network drops). Do not write redundant error handling or check for impossible states in deterministic local code.

---

## 3. Surgical and Non-Invasive Edits
*Limit the footprint of your changes. Touch only the files, lines, and functions that are strictly necessary to accomplish the goal.*

* **Strict Scope Isolation**: Do not "improve," reformat, or refactor adjacent code or files that are outside the scope of the requested change. Leave them exactly as they are.
* **Match Existing Style**: Conform entirely to the existing coding style, naming conventions, directory structures, and import patterns in the repository, even if you prefer a different approach.
* **Flag, Do Not Delete**: If you notice dead, unused, or deprecated code during your work, do not delete it. Instead, flag it to the user or note it in the pull request description.

---

## 4. Goal-Oriented and Verifiable Execution
*Define clear success criteria for every task and verify them programmatically before concluding work.*

* **Failing Test First (Reproduction)**: When fixing a bug, first write a test case or script that reproduces the bug and fails. Verify that the bug is fixed only when that specific test case passes.
* **Pre/Post Regression Checks**: Before and after making any change, run existing verification suites (linting, type checking, or unit tests) to ensure zero regressions are introduced.
* **Explicit Success Criteria**: Avoid vague definitions of done. Translate tasks into concrete, verifiable outcomes:
  * *Vague*: "Implement API endpoint validation."
  * *Verifiable*: "Write an integration test that sends invalid JSON to the endpoint, verify it returns 422 Unprocessable Entity, then make the test pass."
* **Test Structure**: All backend Python test suites must live in the `api/tests/` directory, use `pytest` assertions, and name test files with the `test_` prefix (e.g., `test_rag_pipeline.py`). All tests must be runnable in isolation and should mock network calls to external APIs.

---

## 5. Frontend Structure & Isolation (`client/`)
*The frontend owns UI/UX, routing, state management, and presentational data fetching. It must never handle server-side secrets or privileged business logic.*

### Architectural Boundaries
* **No Secrets**: Under no circumstances should service role keys, privileged keys, or backend secrets be committed to or loaded by the client.
* **No Privileged Business Logic**: Avoid executing sensitive business rules or database integrity validations on the client. Trust only the backend's validations.

### Directory Roles & Patterns (Pages Orchestrate, Hooks Implement, Components Render)
* **`client/pages/`**: Route-level containers.
  * **Allowed**: Handle client-side routing, compose UI sections, wire custom hooks, and manage overall loading/error UI states.
  * **Forbidden**: Direct API fetch wiring or database queries.
* **`client/components/`**: Reusable presentational building blocks.
  * **Allowed**: Stylings, accessibility, local component UI state, and render props.
  * **Forbidden**: Executing API calls (`fetch`/`axios`), or mutating global application state directly. They must be testable solely by passing props.
* **`client/hooks/`**: Reusable stateful logic.
  * **Allowed**: Session handling, data fetching, global/derived state, and side-effects.
* **`client/lib/`**: Pure utilities and client-side helper libraries.
  * **Generalised Helper Rule**: All pure utility functions, text formatters, parsing helper functions, and non-stateful calculations must be isolated from page/container components and placed under `client/src/lib/` (or `client/src/utils/`) organized by theme.
  * **JSDoc Convention**: All TypeScript helper functions, utilities, and components must be documented using standard JSDoc comment blocks for parameters, returns, and function purposes.
* **`client/integrations/`**: Third-party SDK wrappers.

### Best Practices
* **Container/Presenter Split**: If a component grows large or complex, separate it into a presenter (pure render component) and a container (logic component).
* **Data Fetching**: Prefer React Query (or native state management libraries) for server state management. Do not use ad-hoc `useEffect` calls to fetch data.
* **No JSX Data Transformations**: Format, filter, and transform data inside custom hooks or library helpers before passing them to JSX.

---

## 6. Backend Structure & Layering (`api/`)
*The backend must enforce a strict separation of concerns between route handling, business workflows, and data access.*

### Endpoint / Route Layer (`api/routes/`)
* **Responsibilities**: Parse and validate request bodies, call service layer functions, shape response formats, and map exceptions to HTTP status codes.
* **Prohibited Inline**: Raw database queries, building LLM prompts, or copy-pasting API call logic (e.g., `httpx` setups) inside routes is strictly forbidden.
* **Domain Partitioning**: Split routes by domain (e.g., `api/routes/messages.py`). `api/index.py` (or `main.py`) must remain as the lightweight app entrypoint only.

### Service Layer (`api/services/` or `api/`)
* **Responsibilities**: Enforce workflow and domain logic (e.g., `api/message_service.py`).
* **Data Retrieval**: Fetch external or local data via repositories or dedicated client wrappers. Do not query data sources directly inline inside other business services.

### Data Access Layer (`api/utils/` or `api/repositories/`)
* **Responsibilities**: Centralize external connections and database REST calls behind clean, defined boundaries (e.g., `api/utils/supabase_client.py`). 
* **Scaling**: If data access logic grows, modularize it into repositories (e.g., `api/repositories/`), but maintain a single, consolidated entry point for database communication.
* **Latency Monitoring & Performance**: For recording latencies of various service steps (such as search, rerank, or prompt prep), use the reusable `@time_it` decorator from `api/utils/time.py`. Do not write manual start/stop stopwatch code inside endpoints or service routes. The decorator supports both synchronous and asynchronous functions and returns a tuple `(result, duration_ms)`.

### Schemas and API Contracts (`api/schemas/`)
* **Pydantic Validation**: All request and response payloads must enforce schemas defined using Pydantic models under `api/schemas/`.
* **Consistent Naming**: Keep variable names consistent between DB schema, API response, and frontend types (e.g., `client_id`, `phone_number`).
* **Database Encapsulation**: Never expose database structures or internal column names directly in API responses without mapping them to the API schema.
* **LLM Modularization**: Group all agentic logic, prompts, and LLM integrations under a clean `api/llm/` module.

---

## 7. Externalized Configuration & Prompts (No Hardcoding)
*Never hardcode configuration variables, API endpoints, model identifiers, or LLM prompts inside source code files.*

* **Sensitive Secrets & Endpoints**: All API credentials (keys, secrets) and environment-specific endpoints/URLs (e.g., search, rerank, or LLM base URLs) must be loaded dynamically from **Environment Variables** (or via a `.env` file for local development). DO NOT read .env file as this will take my secret. If there's an error in missing key or etc. flag that to the developer. 
* **Application Settings**: Non-sensitive settings like model identifiers, timeouts, maximum limits, and ports must be loaded from **Configuration Files** or config utilities (e.g., a Pydantic Settings class or a JSON/YAML configuration file) rather than hardcoded inline.
* **LLM Prompts & Templates**: System prompts, instructions, and prompt templates must reside in separate **Prompt Resource Files** (e.g., `.txt` or `.yaml` template files under a designated directory like `api/prompts/` or `api/resources/`) and read at runtime, not embedded as raw multiline strings inside Python or JS source code.

---

## 8. Git Instructions & Best Practices
*Maintain a clean, logical, and descriptive git history. Code is read far more often than it is written.*

* **Atomic Commits**: Commit changes in small, logical chunks. Do not group multiple unrelated features, fixes, or styling changes into a single massive commit.
* **Conventional Commits**: Use the Conventional Commits structure for all commit messages. 
  * Format: `<type>(<scope>): <short description in imperative mood>`
  * Examples: 
    * `feat(api): add Cohere reranking service`
    * `fix(client): fix latency visual layout overflow on small screens`
    * `docs(repo): update API key environment variables in README`
* **Clean Diff Review**: Before staging or committing, run `git diff` to review all changes. Ensure no local temporary files, print statement debug lines, hardcoded keys, or draft notes are committed.
* **Never Commit Secrets**: Ensure `.env` or any secret key file is included in `.gitignore` and never committed to the remote repository.
