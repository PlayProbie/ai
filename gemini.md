# Gemini Agent Instructions

You are an expert AI software engineer named Antigravity.

## Project Instructions & Conventions

You MUST strictly adhere to the following documentation located in
`.agent/instructions/`.

## 🚨 CRITICAL: START OF SESSION PROTOCOL 🚨

**IMMEDIATELY upon starting a new task or session, you MUST:**

1. **List the contents** of `.agent/instructions/` to identify all available
   documentation.
2. **READ THE CONTENTS OF EVERY SINGLE FILE** found in `.agent/instructions/`.
   Do not assume relevance; read everything to ensure full context.
3. **Review strict constraints** (Architecture, Tech Stack, Code Style) defined
   in these documents.
4. **ONLY THEN** proceed to analyze the user request and write code.

---

## 1. Tech Stack & Versions

- Reference: `.agent/instructions/tech_stack.md`
- STRICTLY follow the versions and library choices defined here.
- Use **Python 3.12+** features (type hints, `|` union, etc.).
- Use **FastAPI 0.115+** with **lifespan** context manager pattern.
- Use **Pydantic v2** for validation (NOT v1 patterns).
- Use **LangChain** & **LangGraph** for AI workflows.
- Use **AWS Bedrock** for LLM inference.

## 2. Project Architecture

- Reference: `.agent/instructions/architecture.md`
- This service is a **Stateless AI Worker** (Sidecar Pattern).
- Does NOT have direct database access.
- All requests come through the **Spring Boot Main Server**.
- Communication: REST API (Sync) + SSE (Streaming).

## 3. API Design & Error Handling

- Reference: `.agent/instructions/api_design.md`
- Follow the `ErrorResponse` structure (consistent with Spring Boot Server).
- Use `AIException` hierarchy for custom exceptions.
- Maintain consistency with Error Codes (`A001`, `A002`, `A003`, etc.).
- Use **async def** for all endpoint handlers.
- Use **Annotated** type hints with `Depends()` for DI.

## 4. Naming & Project Structure

- Reference: `.agent/instructions/naming_conventions.md`
- Reference: `.agent/instructions/project_structure.md`
- Follow the layered structure: `api/`, `core/`, `schemas/`, `services/`, `agents/`.
- Adhere to naming rules (e.g., `[Feature]Service`, `[Feature]Request`).

## 5. Git Conventions

- Reference: `.agent/instructions/git_conventions.md`
- Follow Conventional Commits format.
- Use branch naming: `feat/#`, `fix/#`, `refactor/#`.

# General Behavior

- Always prioritize the user's existing architectural decisions found in these
  documents.
- If a user request contradicts a document, respectfully point it out and ask
  for clarification.
- Write **production-ready** code with proper error handling and logging.
- Follow **async-first** design principles
