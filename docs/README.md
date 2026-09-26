# Echoface documentation index

Organised by role. Start with the [User Manual](user-manual.md) if you
just want to use the tool, or [Installation](ops/installation-deployment.md)
to set it up.

## Business Analyst
- [Business Requirements Document](business/brd.md)
- [Software Requirements Specification](business/srs.md)
- [User Stories](business/user-stories.md)
- [Use Cases](business/use-cases.md)

## Project Manager
- [Project Charter](pm/project-charter.md)
- [Roadmap / Milestones (M1–M8 + future)](pm/roadmap.md)
- [RAID Log](pm/raid-log.md)
- [Release Plan](pm/release-plan.md)
- [Stakeholders & RACI](pm/stakeholders-raci.md)

## Architect
- [Software Architecture (C4 + Mermaid)](architecture/software-architecture.md)
- [Data Flow](architecture/data-flow.md)
- [Job / Stage State Machine](architecture/job-state-machine.md)
- [Deployment View](architecture/deployment-view.md)
- [Tech Stack](architecture/tech-stack.md)
- Architecture Decision Records: [0001](architecture/adr/0001-separate-venvs.md)
  · [0002](architecture/adr/0002-subprocess-runners.md)
  · [0003](architecture/adr/0003-python-3.14-cu128.md)
  · [0004](architecture/adr/0004-two-pass-loudnorm.md)
  · [0005](architecture/adr/0005-idempotent-stage-hashing.md)
  · [0006](architecture/adr/0006-consent-gate.md)
  · [0007](architecture/adr/0007-dummy-engines.md)

## QA
- [Test Strategy](qa/test-strategy.md)
- [Test Plan](qa/test-plan.md)
- [Test Case Catalogue](qa/test-cases.md)
- [Requirements Traceability Matrix](qa/traceability-matrix.md)
- [Defect Log](qa/defect-log.md)
- [Quality Checklist](qa/quality-checklist.md)

## Developer
- [../CONTRIBUTING.md](../CONTRIBUTING.md) (dev setup, PR checklist)
- [Coding Standards](dev/coding-standards.md)
- [Module / API Reference](dev/module-reference.md)
- [Adding a Stage or Engine](dev/adding-a-stage-or-engine.md)

## Ops / DevOps
- [Installation / Deployment Guide](ops/installation-deployment.md)
- [Configuration Reference](ops/configuration-reference.md)
- [Runbook](ops/runbook.md)
- [Troubleshooting](ops/troubleshooting.md)
- [Performance / VRAM Guide](ops/performance-vram-guide.md)

## Security and Compliance
- [../SECURITY.md](../SECURITY.md) (vulnerability reporting)
- [Threat Model](security/threat-model.md)
- [Licence Matrix](security/license-matrix.md)
- [Responsible Use & Consent Policy](security/responsible-use-consent-policy.md)
- [AI Disclosure Policy](security/ai-disclosure-policy.md)

## Everyone
- [User Manual](user-manual.md)
- [Improvements & Known Issues](project/improvements-and-known-issues.md)
- [../CHANGELOG.md](../CHANGELOG.md)
