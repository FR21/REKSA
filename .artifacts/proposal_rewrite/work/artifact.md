# Proposal REKSA rewrite contract

## References

- Structural source: `/home/wielio/Downloads/REKSA_Proposal_GEMASTIK_XIX_2026 (2).docx`
- SHA-256: `9e9ebe28c490c281a08c3e0e1cee174b23d1f45a3c44597f1101d134f5e09fe3`
- Source render: `.artifacts/proposal_rewrite/reference_docx`, 23 pages
- Source package: 3 sections, 192 paragraphs, 17 tables, 3 inline images
- Visual inspiration: `/home/wielio/Downloads/Proposal (1).pdf`, 30 pages
- Normative structure: `/home/wielio/Downloads/Panduan-GEMASTIK-2026.pdf`, category chapter I, pages 69-78

## Authority and intended departure

The DOCX controls the official section order, team identity, technical topic, and academic tone. The user explicitly requested a complete rewrite and visual redesign, so its direct formatting and pagination are not preserve-only. The senior proposal informs the rhythm of cover, section openings, diagrams, tables, captions, implementation evidence, and references. The official guide controls required sections and the 30-page ceiling.

## Page and visual system

- A4 portrait, 0.79 inch margins, one column.
- First page is a cover with mandatory logo positions, actual REKSA logo, title, team identity, institution, and year.
- Subsequent pages use a quiet navy running header and muted page-number footer.
- Academic narrative uses Times New Roman, 11 pt, justified, 1.15-1.20 line spacing.
- Heading 1 uses 15 pt navy, heading 2 uses 12.5 pt navy, heading 3 uses 11.5 pt dark blue.
- Tables use fixed geometry, navy headers, white body, light-blue alternate emphasis only when needed.
- Figures use centered bordered placeholders with a precise capture/drawing instruction and a numbered caption. Existing REKSA logo and two prototype photographs are reusable evidence.

## Content flow and slot map

1. Cover: rewrite and redesign; preserve team data; add mandatory logo placeholders.
2. Abstract and keywords: rewrite to reflect offline-first implementation, cloud path, AI baseline status, and human verification.
3. Table of contents: generated from real heading styles with update-fields enabled.
4. Background: rewrite with national K3 evidence, near-miss reporting problem, BLE literature, and the specific solution gap.
5. Urgency and benefits: rewrite around judging criteria, stakeholder value, SDG 8 and SDG 9, novelty, and state-of-the-art comparison.
6. Development method: rewrite as an evidence-oriented engineering process covering AI, embedded systems, IoT, and validation.
7. Prototype/model design: replace future-tense cloud architecture with the implemented HiveMQ TLS to Pub/Sub to Cloud Run and Firebase path; document power, pinout, MQTT contract, durable buffer, ACK, deduplication, software stack, and AI architecture.
8. Functional analysis, operation, and performance: rewrite with observed integration evidence, planned controlled tests, safety taxonomy, limits, and measurable targets.
9. Implementation plan and progress: mark completed work accurately; retain remaining dataset/model/field-validation work; include timeline, cost, risks, and mitigations.
10. Photos and 50 percent implementation: reuse two prototype photos and add explicit placeholders for wiring, serial log, HiveMQ, bridge, Cloud Run, and dashboard evidence.
11. Video link: preserve current link with a final-submission reminder.
12. References: rebuild consistently and remove unsupported or redundant entries.

## Fidelity and quality gates

- Keep the official order and all required GEMASTIK sections.
- Total pages must not exceed 30.
- No em dash character.
- No unsupported performance claims or invented test metrics.
- Current AI must be labeled `RULE_BASED_BASELINE` and `ADVISORY_ONLY`; ML candidates remain a planned, evidence-gated upgrade.
- Every placeholder must state what visual to insert and what evidence must be visible.
- No password, service-account key, MQTT secret, or private identifier may appear.
- Render every page and inspect for clipping, overlap, broken tables, awkward page breaks, and unreadable placeholders.
