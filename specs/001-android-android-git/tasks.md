---
description: "Task list for Android项目资源包替换构建工具 implementation"
---

# Tasks: Android项目资源包替换构建工具

**Input**: Design documents from `/specs/001-android-android-git/`
**Prerequisites**: plan.md (completed), spec.md (completed), research.md (completed), data-model.md (completed), contracts/ (completed)

**Tests**: Tests are not explicitly requested in the feature specification, so test tasks are OPTIONAL and marked as such.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions
- **Single project**: `src/`, `tests/` at repository root
- All code should be located in `/src` directory per plan.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Create project structure per implementation plan in `src/` directory
- [x] T002 Initialize Python 3.13+ project with FastAPI dependencies in `pyproject.toml`
- [x] T003 [P] Configure code quality tools (ruff, black, mypy) in project configuration
- [x] T004 [P] Create development environment configuration files (`.env.example`, `README.md`)
- [x] T005 [P] Setup basic directory structure: `src/models/`, `src/services/`, `src/api/`, `src/utils/`, `src/config/`, `src/templates/`, `src/static/`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Setup SQLite database with SQLAlchemy 2.0 async in `src/config/database.py`
- [x] T007 [P] Implement base async repository pattern in `src/database/repositories.py`
- [x] T008 [P] Setup FastAPI application structure and middleware in `src/main.py`
- [x] T009 [P] Configure error handling and logging infrastructure in `src/utils/exceptions.py`
- [x] T010 [P] Create base Pydantic models in `src/models/base.py`
- [x] T011 Setup environment configuration management in `src/config/settings.py`
- [x] T012 Create database initialization and migration system in `src/database/init_db.py`

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - 项目配置和资源包上传 (Priority: P1) 🎯 MVP

**Goal**: 用户需要配置Android项目、选择Git分支，并上传资源包到系统中

**Independent Test**: 可以通过测试项目配置界面功能来独立验证，包括项目选择、分支读取和文件上传功能

### Implementation for User Story 1

- [x] T013 [P] [US1] Create AndroidProject model in `src/models/android_project.py`
- [x] T014 [P] [US1] Create ProjectConfig model in `src/models/project_config.py`
- [x] T015 [US1] Implement AndroidProjectService in `src/services/android_service.py` (depends on T013, T014)
- [x] T016 [US1] Implement FileService for upload handling in `src/services/file_service.py`
- [x] T017 [P] [US1] Create project management API endpoints in `src/api/projects.py`
- [x] T018 [US1] Implement file upload endpoint in `src/api/files.py`
- [x] T019 [US1] Create Git branch detection utility in `src/utils/git_utils.py`
- [x] T020 [US1] Add resource package validation in `src/utils/validators.py`
- [x] T021 [US1] Create basic HTML frontend with drag-drop interface in `src/templates/index.html`
- [x] T022 [US1] Add frontend JavaScript for file upload in `src/static/js/main.js`
- [x] T023 [US1] Add Tailwind CSS styling in `src/static/css/style.css`

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - 自动化资源替换和构建 (Priority: P1)

**Goal**: 用户点击构建按钮后，系统需要自动执行分支切换检查、资源包验证、资源替换和Gradle构建的完整流程

**Independent Test**: 可以通过模拟整个构建流程来测试，包括分支检查、资源替换验证和构建执行

### Implementation for User Story 2

- [x] T024 [P] [US2] Create BuildTask model in `src/models/build_task.py`
- [x] T025 [P] [US2] Create BuildLog model in `src/models/build_log.py`
- [x] T026 [US2] Implement BuildService for orchestrating builds in `src/services/build_service.py`
- [x] T027 [US2] Create Gradle build executor in `src/utils/gradle_utils.py`
- [x] T028 [US2] Implement Git safety checks in `src/utils/git_utils.py` (extends T019)
- [x] T029 [US2] Create build management API endpoints in `src/api/builds.py`
- [x] T030 [US2] Implement WebSocket for real-time build logs in `src/api/websocket.py`
- [x] T031 [US2] Add build progress tracking and status updates
- [x] T032 [US2] Create resource replacement logic in `src/services/resource_service.py`
- [x] T033 [US2] Integrate build workflow with AndroidProjectService
- [x] T034 [US2] Add build control UI elements to frontend in `src/templates/index.html`
- [x] T035 [US2] Implement real-time log display in frontend JavaScript

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - 构建产物提取和管理 (Priority: P2)

**Goal**: 构建完成后，用户需要能够提取最终的APK产物

**Independent Test**: 可以通过模拟构建完成状态来测试产物提取功能

### Implementation for User Story 3

- [ ] T036 [P] [US3] Create BuildResult model in `src/models/build_result.py`
- [ ] T037 [P] [US3] Create APKFile model in `src/models/apk_file.py`
- [ ] T038 [US3] Implement APK extraction service in `src/services/apk_service.py`
- [ ] T039 [US3] Create build results API endpoints in `src/api/results.py`
- [ ] T040 [US3] Implement file download functionality in `src/api/files.py` (extends T018)
- [ ] T041 [US3] Add APK file detection and metadata extraction
- [ ] T042 [US3] Create build results display UI in frontend
- [ ] T043 [US3] Implement download buttons and file management interface

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently

---

## Phase 6: User Story 4 - Git提交和回滚管理 (Priority: P2)

**Goal**: 构建成功后，用户需要能够对资源更新进行Git提交或将代码回滚到更新前的状态

**Independent Test**: 可以通过模拟构建完成状态和Git操作来测试提交和回滚功能

### Implementation for User Story 4

- [ ] T044 [P] [US4] Create GitOperation model in `src/models/git_operation.py`
- [ ] T045 [P] [US4] Create RepositoryBackup model in `src/models/repository_backup.py`
- [ ] T046 [US4] Implement GitService for commit/rollback operations in `src/services/git_service.py` (extends T019)
- [ ] T047 [US4] Create Git operations API endpoints in `src/api/git.py`
- [ ] T048 [US4] Implement safe Git commit with backup in GitService
- [ ] T049 [US4] Implement Git rollback with restore functionality
- [ ] T050 [US4] Add Git operations history tracking
- [ ] T051 [US4] Create Git operations UI in frontend (commit message input, buttons)
- [ ] T052 [US4] Implement Git operations status display and feedback
- [ ] T053 [US4] Add Git operation results display (commit hash, status)

**Checkpoint**: All user stories should now be independently functional

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T054 [P] Update documentation with implementation details in `README.md`
- [ ] T055 Code cleanup and refactoring across all services
- [ ] T056 Performance optimization for file uploads and build monitoring
- [ ] T057 [P] Add comprehensive error handling and user feedback
- [ ] T058 Security hardening (file validation, path safety, input sanitization)
- [ ] T059 Run quickstart.md validation and update installation guide
- [ ] T060 [P] Add logging configuration and monitoring
- [ ] T061 [P] Implement health check endpoint in `src/api/health.py`
- [ ] T062 Final integration testing and bug fixes

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (US1 & US2 → US3 & US4)
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P1)**: Can start after Foundational - Integrates with US1 but independently testable
- **User Story 3 (P2)**: Can start after Foundational + US2 - Depends on build completion
- **User Story 4 (P2)**: Can start after Foundational + US2 - Depends on build completion

### Within Each User Story

- Models before services
- Services before endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel
- All Foundational tasks marked [P] can run in parallel (within Phase 2)
- Once Foundational phase completes, US1 & US2 can start in parallel (both P1)
- US3 & US4 can also run in parallel after US2 is complete
- All models within a story marked [P] can run in parallel
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1 (MVP Focus)

```bash
# Launch all models for User Story 1 together:
Task: "Create AndroidProject model in src/models/android_project.py"
Task: "Create ProjectConfig model in src/models/project_config.py"

# Launch frontend components in parallel:
Task: "Create basic HTML frontend with drag-drop interface in src/templates/index.html"
Task: "Add frontend JavaScript for file upload in src/static/js/main.js"
Task: "Add Tailwind CSS styling in src/static/css/style.css"

# Launch API endpoints in parallel:
Task: "Create project management API endpoints in src/api/projects.py"
Task: "Implement file upload endpoint in src/api/files.py"
```

---

## Implementation Strategy

### MVP First (User Stories 1 & 2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1
4. Complete Phase 4: User Story 2
5. **STOP and VALIDATE**: Test core workflow independently (project config → resource upload → build)
6. Deploy/demo core functionality

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Core project and upload functionality
3. Add User Story 2 → Test independently → Complete build workflow (MVP!)
4. Add User Story 3 → Test independently → APK extraction and download
5. Add User Story 4 → Test independently → Git commit and rollback
6. Complete Phase 7 → Polish and production readiness

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Project + Upload)
   - Developer B: User Story 2 (Build + Real-time)
3. After US1 & US2 complete:
   - Developer A: User Story 3 (APK extraction)
   - Developer B: User Story 4 (Git operations)
4. Stories complete and integrate independently

---

## Task Count Summary

- **Total Tasks**: 62
- **Phase 1 (Setup)**: 5 tasks
- **Phase 2 (Foundational)**: 7 tasks (CRITICAL)
- **Phase 3 (US1 - MVP)**: 11 tasks
- **Phase 4 (US2 - Core)**: 12 tasks
- **Phase 5 (US3 - APK)**: 8 tasks
- **Phase 6 (US4 - Git)**: 10 tasks
- **Phase 7 (Polish)**: 9 tasks

### Parallelizable Tasks
- **Tasks marked [P]**: 48 tasks (77%)
- **Sequential dependencies**: 14 tasks (23%)

### MVP Scope (User Stories 1 & 2)
- **Tasks for MVP**: 35 tasks (56% of total)
- **Estimated effort**: 2-3 weeks for single developer

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Focus on US1 & US2 for MVP delivery
- Git operations (US4) and APK extraction (US3) are value-add features
- Verify each story works independently before proceeding
- Avoid: vague tasks, same file conflicts, cross-story dependencies that break independence
- All tasks include exact file paths for immediate execution