# Demo slide pack

A 20-slide demo deck for the Bespoke Agentic AI Factory — designs, architecture,
flows and UI mockups.

## Files

| File | Use |
|---|---|
| `ai-factory-demo.pdf` | Present / share (open anywhere) |
| `ai-factory-demo.pptx` | PowerPoint / Google Slides (one full-bleed image per slide) |
| `assets/slide_NN.png` | Individual slide images (1920×1080) |
| `build_deck.py` | Source — regenerates all of the above |

## Regenerate

```bash
pip install matplotlib pillow python-pptx
python docs/slides/build_deck.py
```

## Outline

1. Title
2. Executive summary
3. The problem
4. Capabilities at a glance
5. High-level architecture
6. The 5-stage agentic pipeline
7. Agentic RAG deep dive (hybrid retrieval + graph)
8. Internal source connectors (Confluence / SharePoint)
9. Connector ingestion — sequence flow
10. Evaluation gates
11. AWS Transform Custom — modernisation factory
12. Spring AI modernisation (before / after)
13. Single pane of glass — Grafana *(mockup)*
14. Observability / telemetry pipeline
15. AWS deployment architecture
16. CI/CD with Harness — gated promotion
17. Demo walkthrough — bring it up & ingest *(mockup)*
18. Query → grounded, gated answer *(mockup)*
19. Quality, testing & security
20. Roadmap & next steps

> The slides marked *(mockup)* are high-fidelity representations of the UI /
> terminal output. Capturing them live requires `docker compose up` (Docker was
> not available in the environment that generated this pack).
