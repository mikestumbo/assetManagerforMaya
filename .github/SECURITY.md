# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          | Maya Version      |
| ------- | ------------------ | ----------------- |
| 1.3.x   | :white_check_mark: | Maya 2025+        |
| 1.2.x   | :x:                | Maya 2024-2025    |
| 1.1.x   | :x:                | Maya 2023-2024    |
| < 1.0   | :x:                | No longer supported |

**Current Stable Version:** v1.3.0  
**Upcoming Version:** v1.4.0 (USD Pipeline features)

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow responsible disclosure:

### How to Report

**DO NOT** create a public GitHub issue for security vulnerabilities.

Instead:

1. **Email**: Send details to `mikestumbo@github` with subject line "SECURITY: Asset Manager for Maya"

2. **Include**:
   * Description of the vulnerability
   * Steps to reproduce the issue
   * Maya version and OS
   * Potential impact assessment
   * Suggested fix (if you have one)

3. **Expected Response Time**:
   * Initial acknowledgment: Within 48 hours
   * Status update: Within 7 days
   * Fix timeline: Depends on severity (see below)

### Severity Levels

#### Critical (Fix within 7 days)

* Remote code execution
* Arbitrary file system access outside Maya project
* Data corruption or loss
* Maya crash leading to unsaved work loss

#### High (Fix within 14 days)

* Unauthorized asset access
* File path traversal vulnerabilities
* Memory leaks causing Maya instability
* Authentication bypass (if future features add auth)

#### Medium (Fix within 30 days)

* Information disclosure
* Denial of service (UI freeze)
* Improper error handling exposing system info

#### Low (Fix in next release)

* Minor information leaks
* UI quirks without security impact
* Non-exploitable edge cases

## Security Best Practices for Users

### Safe Asset Management

1. **Trusted Sources Only**
   * Only load assets from trusted directories
   * Be cautious with assets from unknown sources
   * Review file paths before importing

2. **File Permissions**
   * Ensure proper read/write permissions on asset directories
   * Don't run Maya with elevated privileges unless necessary
   * Use network shares with appropriate access controls

3. **Script Execution**
   * Review any Python scripts before execution
   * Asset Manager doesn't execute arbitrary code from assets
   * Be cautious with MEL scripts in scene files

4. **Path Safety**
   * Use absolute paths when possible
   * Be aware of path traversal risks (../../)
   * Validate external file references

### Maya Security Guidelines

1. **Keep Maya Updated**
   * Use Maya 2025 or later for latest security patches
   * Check Autodesk security bulletins regularly

2. **Python Environment**
   * Don't install untrusted Python packages in Maya's environment
   * Use virtual environments for testing

3. **Network Considerations**
   * If using network asset libraries, use secure protocols
   * Consider VPN for remote asset access
   * Implement proper authentication (future feature)

## Known Security Considerations

### Current Implementation

1. **File System Access**
   * Asset Manager accesses local file system for asset scanning
   * No arbitrary path traversal protection yet (planned for v1.5.0)
   * Users should configure trusted directories only

2. **Thumbnail Generation**
   * Uses Maya's playblast/screenshot functionality
   * Requires opening/referencing Maya files
   * Potential for malicious scene files (mitigated by Maya's sandboxing)

3. **Cache System**
   * Thumbnails cached in user's temp directory
   * Cache cleared on app restart
   * No sensitive data stored in cache

4. **No Authentication**
   * Current version has no user authentication
   * Planned for v1.5.0 with team collaboration features
   * All users have equal access to configured asset libraries

### Future Security Features (Roadmap)

* **v1.4.0**: USD Pipeline
  * USD file validation before import
  * Safe path handling for texture references
  * Material conversion sandboxing

* **v1.5.0**: Cloud Integration
  * End-to-end encryption for cloud storage
  * User authentication and authorization
  * Audit logging for asset access
  * Path traversal protection

* **v2.0.0**: Advanced Features
  * Digital signatures for asset verification
  * Malware scanning integration (optional)
  * Role-based access control
  * Secure asset sharing

## Security Update Process

1. **Vulnerability Confirmed**
   * Security team reviews report
   * Severity assigned
   * Fix prioritized

2. **Fix Development**
   * Patch developed in private branch
   * Security review conducted
   * Tests added to prevent regression

3. **Coordinated Disclosure**
   * Fix released with security advisory
   * CVE assigned if applicable (critical issues)
   * Reporter credited (if desired)

4. **User Notification**
   * GitHub security advisory published
   * Release notes include security fixes
   * Users notified via GitHub releases

## Security Testing

### What We Test

* File path validation
* Maya scene file handling
* Python script execution boundaries
* UI input sanitization
* Cache integrity
* Maya API safe usage

### How to Help

Security researchers and users can help by:

* Testing edge cases with unusual file paths
* Reviewing code for potential vulnerabilities
* Reporting suspicious behavior
* Contributing security-focused tests

## Compliance

### Maya/Autodesk Compliance

* Follows [Maya Security Guidelines](https://knowledge.autodesk.com/support/maya)
* Uses only documented Maya APIs
* No binary patching or unsupported modifications
* Respects Maya's security model

### Data Privacy

* No telemetry or usage tracking
* No external network connections (v1.3.0)
* Asset metadata stays local
* No personal data collection

### Open Source Security

* Source code publicly available for audit
* Dependencies reviewed for known vulnerabilities
* Regular dependency updates
* Community security contributions welcome

## Third-Party Dependencies

### Current Dependencies (v1.3.0)

All dependencies are included with Maya 2025+:

* **PySide6**: Qt bindings (maintained by Qt Company)
* **Python 3.10+**: Core interpreter (Python Software Foundation)
* **Maya Python API**: Autodesk-maintained

### USD Pipeline Dependencies (v1.4.0)

* **Pixar USD**: Universal Scene Description library
* **mayaUSD Plugin**: Autodesk's USD integration
* No external dependencies outside Maya/Autodesk ecosystem

## Security Hall of Fame

We recognize security researchers who responsibly disclose vulnerabilities:

* [No reports yet - be the first!]

## Questions?

For non-security questions:

* GitHub Discussions: General questions
* GitHub Issues: Bug reports (non-security)

For security concerns:

* Email: `mikestumbo@github`
* Subject: "SECURITY: Asset Manager for Maya"

---

**Last Updated**: October 16, 2025  
**Version**: 1.0  
**Next Review**: January 2026

---

*We are committed to keeping Asset Manager for Maya secure for the entire Maya community.* 🔒
