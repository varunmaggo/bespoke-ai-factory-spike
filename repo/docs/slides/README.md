# Demo slide pack

A 35-slide demo deck for the Bespoke Agentic AI Factory — designs, architecture,
flows, UI mockups and the wider Cognitive Enterprise Platform vision.

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
20. Roadmap & next steps (the spike) → transition to the platform vision

### Part 2 — the Cognitive Enterprise Platform

21. The Cognitive Enterprise Platform — layered blueprint
22. Business surface — value streams across every function
23. Orchestration layer — the AI Centre of Excellence
24. Operating model — centrally vs decentrally built agents
25. Agent-to-Agent (A2A) collaboration — protocol flow
26. Memory architecture — long-term vs short-term
27. Data foundation & LLMOps — bottom-up pipeline
28. How this spike maps to the platform
29. Security, guardrails & Responsible AI
30. FinOps — cost & performance engine
31. Personas & journeys
32. Maturity model — crawl / walk / run / fly
33. Implementation roadmap — Now / Next / Later
34. Business value & ROI
35. Closing — vision & call to action

> The slides marked *(mockup)* are high-fidelity representations of the UI /
> terminal output. Capturing them live requires `docker compose up` (Docker was
> not available in the environment that generated this pack).
