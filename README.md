# Shared infrastructure

This directory starts the model server (Ollama) used by the labs that need an LLM.
It is **independent** from any other lab repository: every name carries the `mcp-`
prefix so nothing gets mixed up.

> Labs 01-03 do not need Ollama. Start it from lab04 onwards.

## Names

| Resource | Name |
|---|---|
| Compose project | `mcp-infra` |
| Container | `mcp-ollama` |
| Network | `mcp-network` |
| Models volume | `mcp-ollama-data` |
| Host port | `11435` (configurable with `OLLAMA_HOST_PORT`) |

The Compose project name is pinned with `name:` because, by default, Compose uses the
directory name (`infrastructure`), and two repositories with that same directory would
end up sharing a project.

## Usage

```bash
cd infrastructure
cp .env.example .env            # optional: only needed to change the port
docker compose up -d
docker compose ps               # wait for "healthy"
```

Pull a model (the volume is dedicated, it does not share models with other stacks):

```bash
docker exec -it mcp-ollama ollama pull <model>
docker exec -it mcp-ollama ollama list
```

For tool calling, pick a model that supports it; models that predate that feature will not execute tools.

## How labs connect

A lab that needs Ollama joins the network as an external network and reaches the server by service name:

```yaml
services:
  agent:
    networks: [mcp-network]
    environment:
      - OLLAMA_URL            # e.g. http://ollama:11434
networks:
  mcp-network:
    name: mcp-network
    external: true
```

## Stop and clean up

```bash
docker compose down        # keeps the models
docker compose down -v     # also deletes the mcp-ollama-data volume
```