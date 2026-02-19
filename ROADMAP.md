# Asset Manager for Maya - Product Roadmap

> **Strategic Planning Document**  
> Last Updated: December 22, 2025  
> Current Version: v1.5.0

---

## 🎯 USD Rig Creator - v1.5.0 Enhancements ✅ IMPLEMENTED

**Status**: ✅ IMPLEMENTED in v1.5.0 | **Completed**: December 2025

The USD Rig Creator (`maya_rig_exporter.py` / `maya_rig_importer.py`) exports Maya rig data to `.mrig` format and reimports onto USD geometry. All 6 planned enhancements have been implemented:

### Enhancement 1: Progress Callback 📊 ✅

**Status**: IMPLEMENTED

- ✅ Added `set_progress_callback()` method to both exporter and importer
- ✅ Progress reporting at each stage (0-100%)
- ✅ Stage names for UI feedback (e.g., "Extracting controllers", "Importing constraints")

### Enhancement 2: Validation Pass ✅ ✅

**Status**: IMPLEMENTED

- ✅ `validate_rig()` method performs pre-export checks
- ✅ Warns about unsupported node types (expressions, scripts, unknown nodes)
- ✅ Reports broken constraints and missing IK handle joints
- ✅ Returns `ValidationResult` with errors, warnings, and unsupported nodes

### Enhancement 3: Space Switches 🔀 ✅

**Status**: IMPLEMENTED

- ✅ `_extract_space_switches()` exports space switch setups
- ✅ Detects parent constraints with multiple targets
- ✅ Finds enum attributes driving constraint weights
- ✅ `_import_space_switches()` recreates via SDKs

### Enhancement 4: Custom Attributes 🏷️ ✅

**Status**: IMPLEMENTED

- ✅ `_extract_custom_attributes()` preserves user-defined attributes
- ✅ Exports type, value, min/max, enum names, keyable/channelBox state
- ✅ `_create_custom_attributes()` recreates on import

### Enhancement 5: Proxy Attributes 🔗 ✅

**Status**: IMPLEMENTED

- ✅ `_extract_proxy_attributes()` captures proxy connections
- ✅ Records source node and attribute for each proxy
- ✅ `_connect_proxy_attributes()` reconnects on import

### Enhancement 6: Undo Support ↩️ ✅

**Status**: IMPLEMENTED

- ✅ Import wrapped in `cmds.undoInfo(openChunk=True, chunkName="Import Rig Data")`
- ✅ Single-step undo of entire rig import
- ✅ Automatic rollback on partial failures

---

## 🎯 Strategic Approach

### **Phase 1: LISTEN (Current - Next 2 Weeks)**

**Primary Goal**: Gather user feedback and identify pain points

- Monitor GitHub Issues and Discussions
- Collect feedback from v1.3.0 release
- Analyze user workflows and pain points
- Review competitor features
- Identify most requested capabilities

**Success Metrics**:

- 10+ user feedback responses
- Clear understanding of top 3 pain points
- Validated feature priorities

---

## 🚀 v1.4.0 - Quick Wins (Target: Q1 2026)

**Theme**: Enhanced Asset Management & Search

### **Feature 1: Smart Search Enhancement** 🔍

**Priority**: HIGH | **Effort**: LOW | **Impact**: HIGH

**Capabilities**:

- Fuzzy search with typo tolerance
- Multi-field search (tags, metadata, file type, artist)
- Recent searches history
- Search suggestions as you type
- Advanced filters (date ranges, size, type)

**Technical Approach**:

- Extend `ILibraryService` with enhanced search methods
- Implement fuzzy matching algorithm (Levenshtein distance)
- Add search history persistence
- Create search suggestions service

**User Value**:

- Find assets faster (50% time savings)
- More forgiving search (typos won't block results)
- Learn from past searches

---

### **Feature 2: Asset Version Control** 🎯

**Priority**: HIGH | **Effort**: MEDIUM | **Impact**: HIGH

**Capabilities**:

- Track asset versions (v1, v2, v3, etc.)
- Version comparison view (side-by-side thumbnails)
- Rollback to previous versions
- Version history timeline
- Version notes/comments

**Technical Approach**:

- Add `AssetVersion` model to data layer
- Extend `IAssetRepository` with version methods
- Create version management service
- Add version UI widget

**User Value**:

- Safety net for experimentation
- Track asset evolution
- Recover from mistakes
- Understand asset history

---

### **Feature 3: Custom Metadata Fields** 📋

**Priority**: HIGH | **Effort**: MEDIUM | **Impact**: HIGH

**Capabilities**:

- User-definable asset properties
- Common presets (Artist, Department, Status, Priority)
- Custom field types (text, dropdown, date, number)
- Filter and sort by custom fields
- Bulk edit custom fields

**Technical Approach**:

- Add `CustomField` schema to metadata model
- Create field definition manager
- Extend metadata extractor for custom fields
- Add custom field editor UI

**User Value**:

- Adapt to studio workflows
- Track studio-specific data
- Better asset organization
- Improved filtering

---

## 🌟 v1.5.0 - Game Changers (Target: Q2 2026)

**Theme**: Collaboration & Cloud Integration

### **Feature 1: Cloud Storage Integration** 🌐

**Priority**: VERY HIGH | **Effort**: HIGH | **Impact**: VERY HIGH

**Capabilities**:

- AWS S3 integration
- Azure Blob Storage support
- Google Cloud Storage support
- Automatic sync across team
- Offline mode with sync queue
- Bandwidth optimization

**Technical Approach**:

- Create `ICloudStorageService` interface
- Implement provider-specific services (S3, Azure, GCS)
- Add sync queue with retry logic
- Create cloud settings dialog
- Implement efficient delta sync

**User Value**:

- Access assets from anywhere
- Automatic team synchronization
- No manual file sharing
- Reduced local storage needs

---

### **Feature 2: Team Collaboration** 👥

**Priority**: VERY HIGH | **Effort**: HIGH | **Impact**: VERY HIGH

**Capabilities**:

- Asset checkout/checkin system
- Lock assets when in use
- Activity feed (who modified what)
- User presence indicators
- Conflict resolution
- Comments and annotations

**Technical Approach**:

- Create `ICollaborationService` interface
- Implement lock management system
- Add activity tracking database
- Create real-time notification system
- Build collaboration UI components

**User Value**:

- Prevent work conflicts
- Team coordination
- Understand project activity
- Faster communication

---

### **Feature 3: Dependency Tracking** 🔗

**Priority**: HIGH | **Effort**: MEDIUM | **Impact**: HIGH

**Capabilities**:

- Automatic dependency detection
- "Used by" / "Uses" relationship graph
- Visual dependency tree
- Dependency validation
- Break-dependency warnings
- Batch dependency updates

**Technical Approach**:

- Create dependency analyzer service
- Parse Maya scene files for references
- Build dependency graph database
- Create graph visualization widget
- Add dependency validation checks

**User Value**:

- Understand asset relationships
- Prevent broken references
- Safe asset modifications
- Better scene understanding

---

## 🚀 v2.0.0 - Future Vision (Target: Q4 2026)

**Theme**: AI-Powered & Next-Gen Features

### **Feature 1: AI-Powered Asset Intelligence** 🤖

**Capabilities**:

- Automatic asset tagging using ML
- Visual similarity search
- Smart asset recommendations
- Automatic categorization
- Content-aware search

**Technical Requirements**:

- TensorFlow or PyTorch integration
- Pre-trained image classification models
- Vector database for similarity search
- GPU acceleration support

---

### **Feature 2: 360° Asset Previews** 🎬

**Capabilities**:

- Turntable animation generation
- Interactive 3D viewer in UI
- Multiple camera angle presets
- Material/shader preview
- Lighting preset variations

**Technical Requirements**:

- Maya viewport capture API
- 360° rotation automation
- Video encoding (H.264/VP9)
- WebGL viewer for 3D preview

---

### **Feature 3: Pipeline Integration** 🔧

**Capabilities**:

- ShotGrid/Shotgun integration
- fTrack support
- Kitsu integration
- Custom pipeline hooks/events
- Render farm integration

**Technical Requirements**:

- REST API client implementations
- OAuth authentication
- Webhook system
- Plugin architecture for custom pipelines

---

## 📊 Feature Priority Matrix

| Feature | Impact | Effort | Priority | Version |
| ------- | ------ | ------ | -------- | ------- |
| Smart Search | HIGH | LOW | 1 | v1.4.0 |
| Version Control | HIGH | MEDIUM | 2 | v1.4.0 |
| Custom Metadata | HIGH | MEDIUM | 3 | v1.4.0 |
| Cloud Storage | VERY HIGH | HIGH | 4 | v1.5.0 |
| Team Collaboration | VERY HIGH | HIGH | 5 | v1.5.0 |
| Dependency Tracking | HIGH | MEDIUM | 6 | v1.5.0 |
| AI Features | REVOLUTIONARY | VERY HIGH | 7 | v2.0.0 |
| 360° Previews | HIGH | HIGH | 8 | v2.0.0 |
| Pipeline Integration | VERY HIGH | VERY HIGH | 9 | v2.0.0 |

---

## 🎨 Architecture Evolution

### **v1.4.0 Architecture Additions**

```text
src/
├── services/
│   ├── search_service_impl.py (NEW)
│   ├── version_control_service_impl.py (NEW)
│   └── custom_metadata_service_impl.py (NEW)
├── core/
│   ├── interfaces/
│   │   ├── search_service.py (NEW)
│   │   ├── version_control_service.py (NEW)
│   │   └── custom_metadata_service.py (NEW)
│   └── models/
│       ├── asset_version.py (NEW)
│       └── custom_field.py (NEW)
└── ui/
    ├── dialogs/
    │   ├── version_history_dialog.py (NEW)
    │   └── custom_fields_editor.py (NEW)
    └── widgets/
        └── version_comparison_widget.py (NEW)
```

---

## 🧪 Testing Strategy

### **v1.4.0 Testing Requirements**

**Search Enhancement**:

- Unit tests for fuzzy matching algorithm
- Integration tests for multi-field search
- Performance tests (10k+ assets)
- UI tests for search suggestions

**Version Control**:

- Unit tests for version tracking
- Integration tests for rollback functionality
- Storage tests for version data
- UI tests for version comparison

**Custom Metadata**:

- Unit tests for field definitions
- Integration tests for metadata persistence
- Validation tests for field types
- UI tests for field editor

---

## 📝 Documentation Plan

### **New Documentation Needed**

**v1.4.0**:

- Search syntax guide
- Version control workflow
- Custom fields tutorial
- Migration guide from v1.3.0

**v1.5.0**:

- Cloud storage setup guide
- Team collaboration best practices
- Dependency management guide

---

## 💭 Open Questions

**To Research & Decide**:

1. **Version Storage**: Store versions as separate files or use database?
2. **Cloud Providers**: Which cloud provider to prioritize first?
3. **Collaboration Backend**: Build custom or use existing service (Firebase, Supabase)?
4. **AI Models**: Pre-trained or train custom models?
5. **3D Viewer**: Embed in Qt or use web-based viewer?
6. **Pricing Model**: Keep free or introduce cloud storage tiers?

---

## 🎯 Success Metrics

### **v1.4.0 Goals**

- Search speed: < 100ms for 10k assets
- Version rollback: < 5 seconds
- Custom fields: Support 50+ field definitions
- User satisfaction: 4.5+ stars on feedback
- Adoption: 1000+ downloads in first month

---

## 🔄 Iterative Development

**Process**:

1. **Listen**: Gather user feedback (ongoing)
2. **Plan**: Prioritize features based on feedback
3. **Design**: Create detailed specifications
4. **Build**: Implement with SOLID principles
5. **Test**: Comprehensive testing (unit + integration)
6. **Document**: User guides and API docs
7. **Release**: Staged rollout with beta testing
8. **Monitor**: Track metrics and feedback
9. **Iterate**: Continuous improvement

---

## 📞 Feedback Channels

**How to Influence Roadmap**:

- GitHub Issues: Feature requests
- GitHub Discussions: Ideas and feedback
- Email: Direct feature suggestions
- User surveys: Periodic feedback collection

---

## 🏆 Long-Term Vision

**Asset Manager for Maya 2030**:

- Industry-standard asset management
- Used in major studios worldwide
- AI-powered intelligent workflows
- Seamless team collaboration
- Cloud-first architecture
- Extensible plugin ecosystem
- Open-source community contributions

---

*This roadmap is a living document. Priorities may shift based on user feedback, technical discoveries, and market changes.*

**Last Review**: October 15, 2025  
**Next Review**: January 1, 2026
