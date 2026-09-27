# Benchmark Command Schema

Allowed operations:

- `TURN`: signed degrees, positive = right, negative = left, |value| <= 180
- `FWD`: millimetres, 0 < value <= 2000
- `BACK`: millimetres, 0 < value <= 1000
- `STOP`: must be the final command

Maximum command count: 12.

The benchmark-facing LLM schema is object based so that it can later be represented
reliably with provider-native structured output / JSON schema.
