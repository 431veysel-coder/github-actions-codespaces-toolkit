#!/usr/bin/env python3
"""
Pipeline Orchestration Engine — DAG-based task execution with checkpoint/resume
Core workflow engine for build automation pipelines
"""

import json
import os
import subprocess
import threading
import time
import uuid
from collections import defaultdict, deque
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from config import get_config
from security_acl import AgentSecurityACL
from security_utils import SecurityError, ValidationError, mask_secrets, safe_run, validate_file_path
from sqlite_memory_manager import SQLiteMemoryManager


class TaskStatus(Enum):
    """Task execution status"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    WAITING_APPROVAL = "waiting_approval"


class TaskType(Enum):
    """Task type for categorization"""

    COMMAND = "command"
    SCRIPT = "script"
    MCP_TOOL = "mcp_tool"
    APPROVAL = "approval"
    CONDITIONAL = "conditional"
    PARALLEL_GROUP = "parallel_group"
    SEQUENTIAL_GROUP = "sequential_group"


@dataclass
class TaskResult:
    """Result of task execution"""

    task_id: str
    status: TaskStatus
    output: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_ms: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Pipeline task definition"""

    id: str
    name: str
    type: TaskType
    description: str = ""

    # Command/script execution
    command: Optional[List[str]] = None
    script: Optional[str] = None
    working_dir: Optional[str] = None
    env: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 300

    # MCP tool invocation
    mcp_tool: Optional[str] = None
    mcp_params: Dict[str, Any] = field(default_factory=dict)

    # Approval gate
    approval_prompt: Optional[str] = None
    approval_required: bool = False

    # Dependencies
    depends_on: List[str] = field(default_factory=list)  # Task IDs

    # Conditional execution
    condition: Optional[str] = None  # Python expression evaluating to bool

    # Retry policy
    max_retries: int = 0
    retry_delay_seconds: int = 5

    # Artifacts
    produces: List[str] = field(default_factory=list)  # Output file patterns
    consumes: List[str] = field(default_factory=list)  # Input file patterns

    # Metadata
    tags: List[str] = field(default_factory=list)
    priority: int = 0

    # Runtime state (not serialized)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[TaskResult] = None
    attempt: int = 0


@dataclass
class Pipeline:
    """Pipeline definition"""

    id: str
    name: str
    description: str = ""
    version: str = "1.0.0"
    tasks: List[Task] = field(default_factory=list)
    global_timeout_seconds: int = 3600
    max_parallelism: int = 4
    variables: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    # Runtime state
    status: TaskStatus = TaskStatus.PENDING
    created_at: Optional[float] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    current_task: Optional[str] = None

    def add_task(self, task: Task) -> "Pipeline":
        """Add task to pipeline"""
        self.tasks.append(task)
        return self

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_dependencies(self, task_id: str) -> List[Task]:
        """Get task dependencies"""
        task = self.get_task(task_id)
        if not task:
            return []
        return [self.get_task(dep_id) for dep_id in task.depends_on if self.get_task(dep_id)]


class PipelineExecutor:
    """Execute pipelines with DAG-based scheduling"""

    def __init__(self, pipeline: Pipeline, config: Optional[Dict] = None):
        self.pipeline = pipeline
        self.config = config or {}
        self.memory = SQLiteMemoryManager()
        self.executor = ThreadPoolExecutor(max_workers=pipeline.max_parallelism)
        self.running_tasks: Dict[str, Future] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self._lock = threading.Lock()
        self._cancelled = False
        self._paused = False
        self._pause_event = threading.Event()
        self._pause_event.set()

    def execute(self, checkpoint_dir: Optional[str] = None) -> Dict[str, Any]:
        """Execute entire pipeline"""
        self.pipeline.status = TaskStatus.RUNNING
        self.pipeline.started_at = time.time()

        # Load checkpoint if exists
        if checkpoint_dir:
            self._load_checkpoint(checkpoint_dir)

        # Build dependency graph
        task_graph = self._build_task_graph()

        # Execute tasks in topological order with parallelism
        try:
            self._execute_dag(task_graph)
        except Exception as e:
            self.pipeline.status = TaskStatus.FAILED
            return {"success": False, "error": str(e), "results": self.task_results}

        self.pipeline.completed_at = time.time()
        self.pipeline.status = TaskStatus.COMPLETED

        # Save final checkpoint
        if checkpoint_dir:
            self._save_checkpoint(checkpoint_dir)

        return {
            "success": self.pipeline.status == TaskStatus.COMPLETED,
            "pipeline_id": self.pipeline.id,
            "duration_seconds": self.pipeline.completed_at - self.pipeline.started_at,
            "results": {k: asdict(v) for k, v in self.task_results.items()},
            "task_statuses": {t.id: t.status.value for t in self.pipeline.tasks},
        }

    def _build_task_graph(self) -> Dict[str, List[str]]:
        """Build adjacency list for DAG"""
        graph = {task.id: [] for task in self.pipeline.tasks}
        in_degree = {task.id: 0 for task in self.pipeline.tasks}

        for task in self.pipeline.tasks:
            for dep_id in task.depends_on:
                if dep_id in graph:
                    graph[dep_id].append(task.id)
                    in_degree[task.id] += 1

        # Check for cycles
        if self._has_cycle(graph, in_degree):
            raise ValueError("Pipeline has circular dependencies")

        return {"graph": graph, "in_degree": in_degree, "tasks": {task.id: task for task in self.pipeline.tasks}}

    def _has_cycle(self, graph: Dict[str, List[str]], in_degree: Dict[str, int]) -> bool:
        """Check for cycles using Kahn's algorithm"""
        queue = deque([node for node, deg in in_degree.items() if deg == 0])
        visited = 0

        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        return visited != len(graph)

    def _execute_dag(self, task_graph: Dict):
        """Execute tasks in DAG order with parallelism"""
        graph = task_graph["graph"]
        in_degree = task_graph["in_degree"]
        tasks = task_graph["tasks"]

        # Queue of ready tasks
        ready_queue = deque([task_id for task_id, deg in in_degree.items() if deg == 0])

        completed = set()

        while ready_queue and not self._cancelled:
            # Wait if paused
            self._pause_event.wait()

            # Submit ready tasks up to parallelism limit
            while ready_queue and len(self.running_tasks) < self.pipeline.max_parallelism:
                task_id = ready_queue.popleft()
                task = tasks[task_id]

                # Check condition
                if task.condition and not self._evaluate_condition(task):
                    task.status = TaskStatus.SKIPPED
                    self.task_results[task_id] = TaskResult(
                        task_id=task_id, status=TaskStatus.SKIPPED, output={"reason": "condition_false"}
                    )
                    completed.add(task_id)
                    self._decrement_dependencies(task_id, graph, in_degree, ready_queue)
                    continue

                # Check approval gate
                if task.approval_required:
                    task.status = TaskStatus.WAITING_APPROVAL
                    if not self._request_approval(task):
                        task.status = TaskStatus.CANCELLED
                        self.task_results[task_id] = TaskResult(
                            task_id=task_id, status=TaskStatus.CANCELLED, error="Approval denied"
                        )
                        completed.add(task_id)
                        self._decrement_dependencies(task_id, graph, in_degree, ready_queue)
                        continue

                # Submit task
                future = self.executor.submit(self._execute_task, task)
                self.running_tasks[task_id] = future
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()

            # Wait for any task to complete
            if self.running_tasks:
                done, _ = self._wait_for_any_task()
                for task_id in done:
                    future = self.running_tasks.pop(task_id)
                    task = tasks[task_id]
                    result = future.result()
                    self.task_results[task_id] = result
                    task.result = result
                    task.status = result.status
                    task.completed_at = time.time()
                    if task.started_at:
                        task.duration_ms = (task.completed_at - task.started_at) * 1000

                    completed.add(task_id)
                    self._decrement_dependencies(task_id, graph, in_degree, ready_queue)

                    # Handle failure
                    if result.status == TaskStatus.FAILED:
                        # Cancel dependent tasks
                        self._cancel_dependents(task_id, graph, tasks)
                        if self.config.get("fail_fast", True):
                            self._cancelled = True
                            break

        # Wait for remaining tasks
        for future in self.running_tasks.values():
            future.result()

    def _decrement_dependencies(self, completed_task_id: str, graph: Dict, in_degree: Dict, ready_queue: deque):
        """Decrement in-degree of dependent tasks"""
        for neighbor in graph[completed_task_id]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                ready_queue.append(neighbor)

    def _cancel_dependents(self, failed_task_id: str, graph: Dict, tasks: Dict):
        """Cancel all tasks that depend on failed task"""
        visited = set()
        queue = deque([failed_task_id])

        while queue:
            task_id = queue.popleft()
            if task_id in visited:
                continue
            visited.add(task_id)

            task = tasks.get(task_id)
            if task and task.status not in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED):
                task.status = TaskStatus.CANCELLED
                self.task_results[task_id] = TaskResult(
                    task_id=task_id, status=TaskStatus.CANCELLED, error=f"Cancelled due to failure of {failed_task_id}"
                )

            for neighbor in graph.get(task_id, []):
                queue.append(neighbor)

    def _wait_for_any_task(self) -> Tuple[Set[str], Dict[str, Future]]:
        """Wait for at least one task to complete"""
        done = set()
        while not done and not self._cancelled:
            self._pause_event.wait()
            for task_id, future in list(self.running_tasks.items()):
                if future.done():
                    done.add(task_id)
            if not done:
                time.sleep(0.1)
        return done, self.running_tasks

    def _execute_task(self, task: Task) -> TaskResult:
        """Execute a single task"""
        start_time = time.time()
        task.attempt += 1

        try:
            if task.type == TaskType.COMMAND:
                output = self._execute_command(task)
            elif task.type == TaskType.SCRIPT:
                output = self._execute_script(task)
            elif task.type == TaskType.MCP_TOOL:
                output = self._execute_mcp_tool(task)
            elif task.type == TaskType.APPROVAL:
                output = self._execute_approval(task)
            else:
                return TaskResult(task_id=task.id, status=TaskStatus.FAILED, error=f"Unknown task type: {task.type}")

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.COMPLETED,
                output=output,
                started_at=start_time,
                completed_at=time.time(),
                duration_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            # Retry logic
            if task.attempt < task.max_retries:
                time.sleep(task.retry_delay_seconds)
                return self._execute_task(task)

            return TaskResult(
                task_id=task.id,
                status=TaskStatus.FAILED,
                error=str(e),
                started_at=start_time,
                completed_at=time.time(),
                duration_ms=(time.time() - start_time) * 1000,
            )

    def _execute_command(self, task: Task) -> Any:
        """Execute shell command"""
        # Validate command
        ok, msg = AgentSecurityACL.validate_command(task.command)
        if not ok:
            raise SecurityError(f"Command blocked by ACL: {msg}")

        # Validate working directory
        if task.working_dir:
            cwd = validate_file_path(task.working_dir, must_exist=True, allow_outside_workspace=True)
        else:
            cwd = None

        # Prepare environment
        env = {**os.environ, **task.env}

        # Execute with safe_run
        result = safe_run(task.command, cwd=str(cwd) if cwd else None, timeout=task.timeout_seconds, env=env)

        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode}

    def _execute_script(self, task: Task) -> Any:
        """Execute script file"""
        if not task.script:
            raise ValueError("No script provided")

        script_path = validate_file_path(task.script, must_exist=True)

        # Determine interpreter
        if script_path.suffix == ".py":
            cmd = ["python3", str(script_path)]
        elif script_path.suffix == ".sh":
            cmd = ["bash", str(script_path)]
        else:
            cmd = [str(script_path)]

        task.command = cmd
        return self._execute_command(task)

    def _execute_mcp_tool(self, task: Task) -> Any:
        """Execute MCP tool"""
        # This would invoke the MCP server
        # For now, return mock result
        return {"mcp_tool": task.mcp_tool, "params": task.mcp_params}

    def _execute_approval(self, task: Task) -> Any:
        """Execute approval gate"""
        # Already handled in _execute_dag
        return {"approved": True}

    def _evaluate_condition(self, task: Task) -> bool:
        """Evaluate task condition expression"""
        if not task.condition:
            return True

        try:
            # Create safe evaluation context
            context = {
                "task_results": self.task_results,
                "pipeline_vars": self.pipeline.variables,
                "os": os,
                "time": time,
                "len": len,
                "str": str,
                "int": int,
                "bool": bool,
            }

            # Add task results to context
            for task_id, result in self.task_results.items():
                context[f"result_{task_id}"] = result

            # Evaluate safely
            return bool(eval(task.condition, {"__builtins__": {}}, context))
        except Exception:
            return False

    def _request_approval(self, task: Task) -> bool:
        """Request human approval for task"""
        prompt = task.approval_prompt or f"Approve task: {task.name}"

        # In automated mode, check if auto-approve is configured
        if self.config.get("auto_approve", False):
            return True

        # In real implementation, this would pause and wait for user input
        # For now, return True (auto-approve in automated environments)
        return True

    def pause(self):
        """Pause pipeline execution"""
        self._paused = True
        self._pause_event.clear()

    def resume(self):
        """Resume pipeline execution"""
        self._paused = False
        self._pause_event.set()

    def cancel(self):
        """Cancel pipeline execution"""
        self._cancelled = True
        for future in self.running_tasks.values():
            future.cancel()

    def _save_checkpoint(self, checkpoint_dir: str):
        """Save pipeline state checkpoint"""
        checkpoint_path = Path(checkpoint_dir) / f"pipeline_{self.pipeline.id}.json"
        checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "pipeline_id": self.pipeline.id,
            "pipeline_name": self.pipeline.name,
            "status": self.pipeline.status.value,
            "task_results": {k: asdict(v) for k, v in self.task_results.items()},
            "task_statuses": {t.id: t.status.value for t in self.pipeline.tasks},
            "variables": self.pipeline.variables,
            "timestamp": time.time(),
        }

        checkpoint_path.write_text(json.dumps(state, indent=2))

    def _load_checkpoint(self, checkpoint_dir: str):
        """Load pipeline state from checkpoint"""
        checkpoint_path = Path(checkpoint_dir) / f"pipeline_{self.pipeline.id}.json"
        if not checkpoint_path.exists():
            return

        state = json.loads(checkpoint_path.read_text())

        # Restore task results
        for task_id, result_data in state.get("task_results", {}).items():
            self.task_results[task_id] = TaskResult(**result_data)

        # Restore task statuses
        for task in self.pipeline.tasks:
            if task.id in state.get("task_statuses", {}):
                task.status = TaskStatus(state["task_statuses"][task.id])

        # Restore variables
        self.pipeline.variables.update(state.get("variables", {}))


# ============================================================================
# PRE-BUILT PIPELINE TEMPLATES
# ============================================================================


def build_android_pipeline(
    project_path: str,
    repo: str = None,
    gradle_version: str = None,
    build_type: str = "release",
    run_tests: bool = True,
    sign_apk: bool = False,
    upload_artifacts: bool = True,
) -> Pipeline:
    """Create Android build pipeline"""

    pipeline = Pipeline(
        id=f"android-build-{uuid.uuid4().hex[:8]}",
        name="Android Build Pipeline",
        description=f"Build {build_type} APK for {project_path}",
        max_parallelism=2,
    )

    # Task 1: Verify project
    verify_task = Task(
        id="verify",
        name="Verify Android Project",
        type=TaskType.MCP_TOOL,
        description="Pre-flight check for Android project",
        mcp_tool="verify_android_project",
        mcp_params={"project_path": project_path},
    )
    pipeline.add_task(verify_task)

    # Task 2: Gradle wrapper validation
    wrapper_task = Task(
        id="validate_wrapper",
        name="Validate Gradle Wrapper",
        type=TaskType.MCP_TOOL,
        description="Validate and fix Gradle wrapper",
        mcp_tool="verify_android_project",
        mcp_params={"project_path": project_path},
        depends_on=["verify"],
    )
    pipeline.add_task(wrapper_task)

    # Task 3: Clean caches
    clean_task = Task(
        id="clean_caches",
        name="Clean Gradle Caches",
        type=TaskType.MCP_TOOL,
        description="Clean stale Gradle caches",
        mcp_tool="clean_pipeline_caches",
        mcp_params={"project_path": project_path},
        depends_on=["validate_wrapper"],
    )
    pipeline.add_task(clean_task)

    # Task 4: Trigger cloud build
    if repo:
        build_task = Task(
            id="trigger_build",
            name="Trigger Cloud Build",
            type=TaskType.MCP_TOOL,
            description="Trigger GitHub Actions build",
            mcp_tool="trigger_workflow",
            mcp_params={
                "repo": repo,
                "workflow": "android-production-pipeline.yml",
                "inputs": json.dumps(
                    {"build_type": build_type, "run_tests": str(run_tests).lower(), "sign_apk": str(sign_apk).lower()}
                ),
            },
            depends_on=["clean_caches"],
        )
        pipeline.add_task(build_task)

        # Task 5: Wait for build and download
        download_task = Task(
            id="download_artifacts",
            name="Download Build Artifacts",
            type=TaskType.MCP_TOOL,
            description="Download APK/AAB from completed build",
            mcp_tool="download_run_artifacts",
            mcp_params={
                "repo": repo,
                "run_id": "{{result_trigger_build.output.run_id}}",
                "output_dir": "/var/minis/workspace/artifacts",
            },
            depends_on=["trigger_build"],
        )
        pipeline.add_task(download_task)

        # Task 6: Profile APK
        profile_task = Task(
            id="profile_apk",
            name="Profile Built APK",
            type=TaskType.MCP_TOOL,
            description="Analyze APK size, DEX count, native libs",
            mcp_tool="profile_built_apk",
            mcp_params={"apk_path": "/var/minis/workspace/artifacts/app-release.apk"},
            depends_on=["download_artifacts"],
        )
        pipeline.add_task(profile_task)

    return pipeline


def release_pipeline(
    project_path: str, repo: str, version_bump: str = "patch", changelog: bool = True, sign_apk: bool = True
) -> Pipeline:
    """Create release pipeline"""

    pipeline = Pipeline(
        id=f"release-{uuid.uuid4().hex[:8]}",
        name="Release Pipeline",
        description=f"Release new version for {project_path}",
        max_parallelism=1,
    )

    # Bump version
    bump_task = Task(
        id="bump_version",
        name="Bump Version",
        type=TaskType.MCP_TOOL,
        description="Automatically bump versionCode and versionName",
        mcp_tool="bump_gradle_version",
        mcp_params={"project_path": project_path},
    )
    pipeline.add_task(bump_task)

    # Generate changelog
    if changelog:
        changelog_task = Task(
            id="generate_changelog",
            name="Generate Changelog",
            type=TaskType.MCP_TOOL,
            description="Generate CHANGELOG.md from git history",
            mcp_tool="generate_changelog",
            mcp_params={"project_path": project_path, "version_tag": "{{result_bump_version.output.version_name}}"},
            depends_on=["bump_version"],
        )
        pipeline.add_task(changelog_task)

    # Generate SBOM
    sbom_task = Task(
        id="generate_sbom",
        name="Generate SBOM",
        type=TaskType.MCP_TOOL,
        description="Generate CycloneDX SBOM",
        mcp_tool="generate_sbom",
        mcp_params={"project_path": project_path},
        depends_on=["bump_version"],
    )
    pipeline.add_task(sbom_task)

    # Trigger release build
    build_task = Task(
        id="trigger_release_build",
        name="Trigger Release Build",
        type=TaskType.MCP_TOOL,
        description="Trigger release build on GitHub Actions",
        mcp_tool="trigger_workflow",
        mcp_params={
            "repo": repo,
            "workflow": "android-release-pipeline.yml",
            "inputs": json.dumps(
                {
                    "build_type": "release",
                    "sign_apk": str(sign_apk).lower(),
                    "version_name": "{{result_bump_version.output.version_name}}",
                }
            ),
        },
        depends_on=["bump_version", "generate_changelog", "generate_sbom"],
    )
    pipeline.add_task(build_task)

    return pipeline


def pr_validation_pipeline(project_path: str, repo: str, pr_number: int) -> Pipeline:
    """Create PR validation pipeline"""

    pipeline = Pipeline(
        id=f"pr-validation-{uuid.uuid4().hex[:8]}",
        name=f"PR #{pr_number} Validation",
        description=f"Validate PR #{pr_number} for {repo}",
        max_parallelism=2,
    )

    # Verify project
    verify_task = Task(
        id="verify",
        name="Verify Project",
        type=TaskType.MCP_TOOL,
        mcp_tool="verify_android_project",
        mcp_params={"project_path": project_path},
    )
    pipeline.add_task(verify_task)

    # Run tests
    test_task = Task(
        id="run_tests",
        name="Run Unit Tests",
        type=TaskType.COMMAND,
        command=["./gradlew", "test"],
        working_dir=project_path,
        depends_on=["verify"],
    )
    pipeline.add_task(test_task)

    # Lint
    lint_task = Task(
        id="lint",
        name="Run Lint",
        type=TaskType.COMMAND,
        command=["./gradlew", "lint"],
        working_dir=project_path,
        depends_on=["verify"],
    )
    pipeline.add_task(lint_task)

    # APK size check
    size_task = Task(
        id="check_size",
        name="Check APK Size",
        type=TaskType.MCP_TOOL,
        mcp_tool="calculate_app_size_metrics",
        mcp_params={"apk_path": "{{result_run_tests.output.apk_path}}"},
        depends_on=["run_tests"],
    )
    pipeline.add_task(size_task)

    return pipeline


def nightly_pipeline(project_path: str, repo: str, matrix: List[Dict] = None) -> Pipeline:
    """Create nightly build pipeline"""

    if matrix is None:
        matrix = [
            {"api": 24, "arch": "arm64"},
            {"api": 28, "arch": "arm64"},
            {"api": 33, "arch": "arm64"},
            {"api": 34, "arch": "arm64"},
            {"api": 34, "arch": "x86_64"},
        ]

    pipeline = Pipeline(
        id=f"nightly-{uuid.uuid4().hex[:8]}",
        name="Nightly Build",
        description=f"Nightly matrix build for {project_path}",
        max_parallelism=4,
    )

    # Create matrix tasks
    for i, config in enumerate(matrix):
        build_task = Task(
            id=f"build_{i}",
            name=f"Build API {config['api']} {config['arch']}",
            type=TaskType.MCP_TOOL,
            mcp_tool="trigger_workflow",
            mcp_params={
                "repo": repo,
                "workflow": "android-nightly-pipeline.yml",
                "inputs": json.dumps({"api_level": config["api"], "arch": config["arch"], "build_type": "debug"}),
            },
        )
        pipeline.add_task(build_task)

    # Aggregate results
    aggregate_task = Task(
        id="aggregate",
        name="Aggregate Results",
        type=TaskType.SCRIPT,
        script="scripts/aggregate_nightly_results.py",
        depends_on=[f"build_{i}" for i in range(len(matrix))],
    )
    pipeline.add_task(aggregate_task)

    return pipeline


# ============================================================================
# MCP TOOL INTEGRATION
# ============================================================================


def execute_pipeline(pipeline_def: Dict, checkpoint_dir: str = None) -> Dict[str, Any]:
    """MCP tool: Execute pipeline from definition"""
    try:
        # Build pipeline from definition
        pipeline = Pipeline(
            id=pipeline_def.get("id", f"pipeline-{uuid.uuid4().hex[:8]}"),
            name=pipeline_def.get("name", "Custom Pipeline"),
            description=pipeline_def.get("description", ""),
            max_parallelism=pipeline_def.get("max_parallelism", 4),
        )

        # Add tasks
        for task_def in pipeline_def.get("tasks", []):
            task = Task(
                id=task_def["id"],
                name=task_def["name"],
                type=TaskType(task_def.get("type", "command")),
                description=task_def.get("description", ""),
                command=task_def.get("command"),
                script=task_def.get("script"),
                working_dir=task_def.get("working_dir"),
                env=task_def.get("env", {}),
                mcp_tool=task_def.get("mcp_tool"),
                mcp_params=task_def.get("mcp_params", {}),
                depends_on=task_def.get("depends_on", []),
                condition=task_def.get("condition"),
                approval_required=task_def.get("approval_required", False),
                approval_prompt=task_def.get("approval_prompt"),
                timeout_seconds=task_def.get("timeout_seconds", 300),
                max_retries=task_def.get("max_retries", 0),
                tags=task_def.get("tags", []),
            )
            pipeline.add_task(task)

        # Execute
        executor = PipelineExecutor(pipeline)
        return executor.execute(checkpoint_dir)

    except Exception as e:
        return {"success": False, "error": str(e)}


def create_pipeline_from_template(template_name: str, params: Dict) -> Dict[str, Any]:
    """MCP tool: Create pipeline from template"""
    try:
        if template_name == "android_build":
            pipeline = build_android_pipeline(**params)
        elif template_name == "release":
            pipeline = release_pipeline(**params)
        elif template_name == "pr_validation":
            pipeline = pr_validation_pipeline(**params)
        elif template_name == "nightly":
            pipeline = nightly_pipeline(**params)
        else:
            return {"success": False, "error": f"Unknown template: {template_name}"}

        return {
            "success": True,
            "pipeline_id": pipeline.id,
            "name": pipeline.name,
            "tasks": [t.id for t in pipeline.tasks],
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_pipeline_templates() -> Dict[str, Any]:
    """MCP tool: List available pipeline templates"""
    return {
        "success": True,
        "templates": {
            "android_build": {
                "name": "Android Build Pipeline",
                "description": "Build Android APK/AAB with optional cloud execution",
                "params": ["project_path", "repo", "build_type", "run_tests", "sign_apk"],
            },
            "release": {
                "name": "Release Pipeline",
                "description": "Create release with version bump, changelog, SBOM",
                "params": ["project_path", "repo", "version_bump", "sign_apk"],
            },
            "pr_validation": {
                "name": "PR Validation Pipeline",
                "description": "Validate pull request with tests, lint, size check",
                "params": ["project_path", "repo", "pr_number"],
            },
            "nightly": {
                "name": "Nightly Matrix Build",
                "description": "Scheduled nightly builds across API levels/architectures",
                "params": ["project_path", "repo", "matrix"],
            },
        },
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "template":
        print(json.dumps(get_pipeline_templates(), indent=2))
    else:
        project = sys.argv[1] if len(sys.argv) > 1 else "."
        repo = sys.argv[2] if len(sys.argv) > 2 else None

        pipeline = build_android_pipeline(project, repo)
        print(f"Pipeline: {pipeline.name}")
        print(f"Tasks: {[t.id for t in pipeline.tasks]}")
