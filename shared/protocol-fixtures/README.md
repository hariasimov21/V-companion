# Protocol fixtures

Canonical examples of WebSocket messages. They are validated by **both** test suites:

- Backend: `apps/backend/tests/test_protocol.py` (Pydantic)
- Desktop: `apps/desktop/src/renderer/src/protocol/parse.test.ts` (TypeScript parser)

When you change the protocol, update these files first; both suites must keep passing.
