---
goal: Update and Maintain CHANGELOG for Asset Manager for Maya
version: 1.0
date_created: 2025-07-23
last_updated: 2025-07-23
status: COMPLETED
owner: assetManagerforMaya Team
tags: [process, documentation, changelog, maintenance]
---

# Introduction

This plan defines the process for updating and maintaining the `CHANGELOG.md` file for the Asset Manager for Maya project. The objective is to ensure all changes, fixes, and releases are documented in a clear, consistent, and machine-parseable format, adhering to the Keep a Changelog and Semantic Versioning standards.

## 1. Requirements & Constraints

- **REQ-001**: All notable changes must be recorded in `CHANGELOG.md` using the Keep a Changelog format.
- **REQ-002**: Each new release must have a dedicated section with version and date.
- **REQ-003**: Unreleased changes must be tracked under the `[Unreleased]` section.
- **REQ-004**: Changelog must be updated before any release is finalized.
- **CON-001**: No changes to changelog structure without explicit approval.
- **CON-002**: All entries must be categorized as Added, Changed, Deprecated, Removed, Fixed, or Security.
- **GUD-001**: Use clear, concise, and unambiguous language for all entries.
- **PAT-001**: Follow Semantic Versioning for all version tags.

## 2. Implementation Steps

| TASK ID    | Description                                                                                                   | File Path                                   | Validation Criteria                                                                                 |
|------------|--------------------------------------------------------------------------------------------------------------|---------------------------------------------|-----------------------------------------------------------------------------------------------------|
| TASK-001   | Add new entries to `[Unreleased]` section for each new feature, change, or fix.                              | CHANGELOG.md                                | New entries appear under correct category in `[Unreleased]` section.                                |
| TASK-002   | Move `[Unreleased]` entries to a new version section upon release, including version number and release date. | CHANGELOG.md                                | New version section created, `[Unreleased]` section cleared, date and version match release.         |
| TASK-003   | Ensure all entries are categorized (Added, Changed, Deprecated, Removed, Fixed, Security).                   | CHANGELOG.md                                | No uncategorized entries present.                                                                   |
| TASK-004   | Validate changelog structure against Keep a Changelog and Semantic Versioning standards.                     | CHANGELOG.md                                | Structure matches official guidelines; headings and formatting are correct.                         |
| TASK-005   | Document any known issues, upgrade notes, and contributing guidelines in dedicated sections.                  | CHANGELOG.md                                | Sections for Known Issues, Upgrade Notes, and Contributing are present and up to date.              |
| TASK-006   | Update links to project repository and documentation as needed.                                               | CHANGELOG.md                                | All links are current and functional.                                                               |

## 3. Alternatives

- **ALT-001**: Use an automated changelog generator. Not chosen to maintain full control and clarity over changelog content.
- **ALT-002**: Maintain changelog in a separate documentation file. Not chosen to centralize all change history in `CHANGELOG.md`.

## 4. Dependencies

- **DEP-001**: Keep a Changelog format specification
- **DEP-002**: Semantic Versioning specification

## 5. Files

- **FILE-001**: `CHANGELOG.md` — Main changelog file for all release and unreleased notes.

## 6. Testing

- **TEST-001**: Automated validation of changelog structure and required sections.
- **TEST-002**: Manual review to ensure all changes are accurately and clearly described.
- **TEST-003**: Link checker to verify all URLs in the changelog are functional.

## 7. Risks & Assumptions

- **RISK-001**: Risk of missing or incomplete entries if process is not followed.
- **ASSUMPTION-001**: All contributors are familiar with changelog guidelines and update process.

## 8. Related Specifications / Further Reading

- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
- [Asset Manager for Maya Repository](https://github.com/mikestumbo/assetManagerforMaya)
