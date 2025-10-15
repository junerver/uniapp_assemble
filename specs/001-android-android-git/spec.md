# Feature Specification: Android项目资源包替换构建工具

**Feature Branch**: `001-android-android-git`
**Created**: 2025-10-15
**Status**: Draft
**Input**: User description: "构建一个应用程序，可以帮助我快速完成对一个Android项目进行资源包替换、构建产物、最终提取产物的。最终产品页面中应该有一个用于拖拽压缩包（资源包）的拖拽框，用于获取项目资源包，一个选择框用于选择Android项目（项目别名、项目目录、项目文件夹名称），一个选择框用于选择git分支（每个Android项目可能有不同的分支，需要通过git读取识别），一个构建按钮。点击构建按钮将会执行如下步骤：1. 会首先检查选中目标Android项目是否可以安全切换到选中的目标分支，如果不能切换则提示手动操作 2. 然后检查拖拽资源包中目录名称是否与，目标Android项目app/src/main/assets/apps目录下的文件夹名称一致，如果不一致则停止执行并显示错误，提示手动操作 3. 3.当名称一致时删除Android项目app/src/main/assets/apps下的文件，将压缩包中的文件复制替换到这个目录，完成资源替换 4. 在Android项目中执行 gradle 构建，即在此目录下执行：./gradlew clean :app:assembleRelease 5. 构建时应该显示gradle的构建日志输出到页面中方便检查 6. 构建完成后页面应该显示一个提取产物的的按钮，点击后检查Android项目下app/build/outputs/apk/release 目录，从中提取apk产物包。我需要更新一条规范，在构建成功后，可以对当前项目进行git提交（即对本次资源更新进行add、commit）、回滚（将代码回滚到更新资源之前，即相当于本次只进行了打包，打包后代码仓库需要恢复原样），这可能需要页面有提交信息输入、提交按钮，回滚按钮等"

## Clarifications

### Session 2025-10-15

- Q: 主要用户角色是什么？ → A: Android开发工程师 - 熟悉Gradle构建、Git操作和Android项目结构
- Q: 数据规模限制是什么？ → A: 中等规模 - 最多20个项目，资源包<500MB，构建历史<1000条
- Q: 安全要求是什么？ → A: 本地访问控制 - 文件权限检查、路径验证、基本数据完整性
- Q: 可观察性要求是什么？ → A: 标准日志记录 - 详细操作日志、构建统计、性能指标
- Q: 错误恢复策略是什么？ → A: 保留状态并提示用户 - 保留当前状态，显示错误并提供恢复选项

## User Scenarios & Testing *(mandatory)*

### User Story 1 - 项目配置和资源包上传 (Priority: P1)

用户需要配置Android项目、选择Git分支，并上传资源包到系统中。这个步骤是整个构建流程的起点，确保所有必要的输入信息都已准备好。

**Why this priority**: 这是整个工具的核心基础功能，没有正确的项目配置和资源包，后续的构建流程无法进行。这是用户与系统交互的第一个接触点。

**Independent Test**: 可以通过测试项目配置界面功能来独立验证，包括项目选择、分支读取和文件上传功能。

**Acceptance Scenarios**:

1. **Given** 用户打开应用程序界面，**When** 用户选择一个有效的Android项目目录，**Then** 系统应该读取并显示该项目的所有Git分支
2. **Given** 用户选择了Android项目和Git分支，**When** 用户拖拽一个有效的压缩包到拖拽区域，**Then** 系统应该验证文件格式并显示上传成功
3. **Given** 用户上传了无效的文件格式，**When** 系统检测到文件不是压缩包，**Then** 系统应该显示错误提示并要求重新上传

---

### User Story 2 - 自动化资源替换和构建 (Priority: P1)

用户点击构建按钮后，系统需要自动执行分支切换检查、资源包验证、资源替换和Gradle构建的完整流程。这是工具的核心自动化功能。

**Why this priority**: 这是工具的核心价值所在，自动化了原本需要手动执行的多个步骤，显著提升了开发效率。

**Independent Test**: 可以通过模拟整个构建流程来测试，包括分支检查、资源替换验证和构建执行。

**Acceptance Scenarios**:

1. **Given** 用户配置了项目、分支和资源包，**When** 用户点击构建按钮，**Then** 系统首先检查是否可以安全切换到目标分支
2. **Given** 系统确认可以安全切换分支，**When** 系统检查资源包目录名称，**Then** 系统验证资源包中的目录名称与Android项目apps目录下的文件夹名称一致
3. **Given** 资源包验证通过，**When** 系统执行资源替换，**Then** 系统删除原有文件并复制压缩包中的文件到apps目录
4. **Given** 资源替换完成，**When** 系统执行Gradle构建，**Then** 系统运行构建命令并实时显示构建日志
5. **Given** 资源包目录名称不匹配，**When** 系统检测到不一致，**Then** 系统停止执行并显示明确的错误信息

---

### User Story 3 - 构建产物提取和管理 (Priority: P2)

构建完成后，用户需要能够提取最终的APK产物。这个功能确保用户能够获得构建的最终成果。

**Why this priority**: 这是构建流程的最后一步，确保用户能够获得可用的APK文件。虽然是重要功能，但优先级略低于核心构建流程。

**Independent Test**: 可以通过模拟构建完成状态来测试产物提取功能。

**Acceptance Scenarios**:

1. **Given** Gradle构建成功完成，**When** 系统检测到构建完成，**Then** 系统显示提取产物按钮
2. **Given** 用户点击提取产物按钮，**When** 系统扫描构建输出目录，**Then** 系统从app/build/outputs/apk/release目录找到并提取APK文件
3. **Given** 系统找到多个APK文件，**When** 系统处理产物提取，**Then** 系统显示所有找到的APK文件供用户选择下载
4. **Given** 系统在构建输出目录找不到APK文件，**When** 系统扫描完成后，**Then** 系统显示"未找到APK文件"的提示信息

---

### User Story 4 - Git提交和回滚管理 (Priority: P2)

构建成功后，用户需要能够对资源更新进行Git提交或将代码回滚到更新前的状态。这个功能让用户可以选择是否将资源更改永久保存到版本控制中。

**Why this priority**: 这是构建流程完成后的重要选项，让用户能够灵活管理版本控制。虽然重要，但优先级略低于核心构建流程。

**Independent Test**: 可以通过模拟构建完成状态和Git操作来测试提交和回滚功能。

**Acceptance Scenarios**:

1. **Given** Gradle构建成功完成，**When** 系统检测到构建完成，**Then** 系统显示Git操作界面，包含提交信息输入框、提交按钮和回滚按钮
2. **Given** 用户输入提交信息并点击提交按钮，**When** 系统执行Git操作，**Then** 系统对资源更新的文件执行git add和git commit操作
3. **Given** 用户点击回滚按钮，**When** 系统执行Git回滚，**Then** 系统将代码仓库恢复到资源更新之前的状态
4. **Given** Git提交操作成功，**When** 系统完成提交，**Then** 系统显示提交成功消息并提供提交哈希值
5. **Given** Git回滚操作成功，**When** 系统完成回滚，**Then** 系统显示回滚成功消息并恢复到原始状态

---

### Edge Cases

- What happens when 用户选择的项目目录不是有效的Android项目？
- How does system handle Gradle构建过程中出现错误？
- What happens when 用户在构建过程中关闭应用程序？
- How does system handle 网络连接中断导致的Git操作失败？
- What happens when 资源包文件损坏或无法解压？
- How does system handle Git仓库处于detached HEAD状态时的提交操作？
- What happens when 用户尝试回滚但存在未提交的更改？
- How does system handle Git提交信息为空或包含特殊字符的情况？
- What happens when Git操作权限不足或仓库被锁定？

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide 拖拽式文件上传界面用于资源包上传
- **FR-002**: System MUST allow users to select and configure Android项目目录 with alias names
- **FR-003**: System MUST automatically read and display Git分支列表 from selected Android project
- **FR-004**: System MUST validate Git分支切换安全性 before executing build process
- **FR-005**: System MUST compare 资源包目录名称 with Android项目apps目录下的文件夹名称
- **FR-006**: System MUST prevent execution when 目录名称不匹配 with clear error messages
- **FR-007**: System MUST automatically replace 资源文件 in apps目录 with files from uploaded zip package
- **FR-008**: System MUST execute Gradle构建命令 `./gradlew clean :app:assembleRelease` in Android project directory
- **FR-009**: System MUST display 实时构建日志输出 during the build process
- **FR-010**: System MUST enable 提取产物按钮 after successful build completion
- **FR-011**: System MUST scan and extract APK文件 from `app/build/outputs/apk/release` directory
- **FR-012**: System MUST provide 错误处理和用户友好的错误提示 for all failure scenarios
- **FR-013**: System MUST support 项目配置管理 allowing users to save and reuse project configurations
- **FR-014**: System MUST validate 压缩包文件格式 and content before processing
- **FR-015**: System MUST maintain 构建历史记录 for troubleshooting and audit purposes
- **FR-016**: System MUST provide Git操作界面 after successful build completion
- **FR-017**: System MUST allow users to input 自定义提交信息 for Git commits
- **FR-018**: System MUST execute Git提交操作 (git add + git commit) for resource file changes
- **FR-019**: System MUST provide Git回滚功能 to restore repository state before resource replacement
- **FR-020**: System MUST validate Git仓库状态 before performing commit or rollback operations
- **FR-021**: System MUST display Git操作结果 including commit hash and success/failure status
- **FR-022**: System MUST handle Git操作错误 gracefully with user-friendly error messages
- **FR-023**: System MUST backup repository state before resource replacement for potential rollback
- **FR-024**: System MUST support Git分支切换 safety validation before any operations

### Key Entities *(include if feature involves data)*

- **Android项目配置**: 项目别名、项目目录路径、Git仓库信息、项目描述
- **资源包**: 压缩包文件、目录结构、资源文件列表、版本信息
- **构建任务**: 构建ID、项目配置、分支信息、构建状态、构建日志、产物路径
- **构建产物**: APK文件、文件大小、创建时间、下载链接
- **Git操作记录**: 操作类型（提交/回滚）、提交哈希、操作时间、操作状态、提交信息
- **仓库状态备份**: 备份ID、备份时间、恢复点、备份文件路径
- **错误日志**: 错误类型、错误描述、发生时间、解决方案建议

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can complete entire resource replacement and build process in under 5 minutes
- **SC-002**: System reduces manual build time by 80% compared to traditional manual process
- **SC-003**: 95% of builds complete successfully without user intervention
- **SC-004**: System provides clear error messages that allow users to resolve issues without additional support
- **SC-005**: Build process completes within 10 minutes for standard Android projects
- **SC-006**: Users can successfully extract APK files on first attempt in 90% of cases
- **SC-007**: System supports concurrent management of at least 10 different Android projects
- **SC-008**: Resource validation catches configuration errors before build process starts in 99% of cases
- **SC-009**: Git commit operations complete successfully in under 30 seconds in 95% of cases
- **SC-010**: Git rollback operations restore repository state successfully in under 20 seconds in 98% of cases
- **SC-011**: Users can perform Git operations (commit or rollback) without losing work in 99% of cases
- **SC-012**: System prevents Git operations that would result in data loss in 100% of cases