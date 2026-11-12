#!/usr/bin/env python3
"""
Automation Scripts — Rollback, notifications, cleanup, scheduled tasks
"""

import json
import os
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import get_config
from security_utils import SecurityError, safe_run, validate_file_path
from sqlite_memory_manager import SQLiteMemoryManager


@dataclass
class RollbackPlan:
    """Rollback plan for failed deployment"""

    pipeline_id: str
    trigger: str  # "auto", "manual"
    target_version: str
    rollback_steps: List[str]
    status: str = "pending"
    created_at: str = ""
    completed_at: Optional[str] = None


class RollbackManager:
    """Manage automated rollbacks for failed deployments"""

    def __init__(self, project_path: str):
        self.project_path = Path(validate_file_path(project_path, must_exist=True))
        self.config = get_config()
        self.memory = SQLiteMemoryManager()

    def create_rollback_plan(self, pipeline_id: str, failed_task: str, error: str) -> RollbackPlan:
        """Create rollback plan for failed pipeline"""
        # Get last successful version from memory
        last_version = self.memory.get_persistent_record("last_successful_version")
        target_version = last_version.get("version", "previous") if last_version else "previous"

        plan = RollbackPlan(
            pipeline_id=pipeline_id,
            trigger="auto",
            target_version=target_version,
            rollback_steps=[
                f"Revert version to {target_version}",
                f"Re-run pipeline with previous version",
                "Verify deployment health",
                "Notify stakeholders",
            ],
            created_at=datetime.now().isoformat(),
        )

        # Save to memory
        self.memory.save_persistent_record(f"rollback_plan_{pipeline_id}", asdict(plan), category="rollbacks")

        return plan

    def execute_rollback(self, plan: RollbackPlan) -> Dict[str, Any]:
        """Execute rollback plan"""
        results = []

        for step in plan.rollback_steps:
            result = self._execute_step(step)
            results.append({"step": step, "result": result})
            if not result.get("success", False):
                break

        plan.status = "completed" if all(r.get("success") for r in results) else "failed"
        plan.completed_at = datetime.now().isoformat()

        # Save updated plan
        self.memory.save_persistent_record(f"rollback_plan_{plan.pipeline_id}", asdict(plan), category="rollbacks")

        return {"plan": asdict(plan), "results": results}

    def _execute_step(self, step: str) -> Dict[str, Any]:
        """Execute a single rollback step"""
        # This would contain actual rollback logic
        return {"success": True, "output": f"Executed: {step}"}


class NotificationManager:
    """Manage notifications for pipeline events"""

    def __init__(self):
        self.config = get_config()
        self.notification_handlers = {
            "slack": self._send_slack,
            "email": self._send_email,
            "webhook": self._send_webhook,
            "telegram": self._send_telegram,
            "console": self._send_console,
        }

    def send_notification(
        self, event: str, message: str, level: str = "info", channels: List[str] = None, metadata: Dict = None
    ):
        """Send notification to configured channels"""
        channels = (
            channels or getattr(self.config.pipeline, "notification_channels", ["console"])
            if hasattr(self.config, "pipeline")
            else ["console"]
        )

        payload = {
            "event": event,
            "message": message,
            "level": level,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {},
        }

        results = {}
        for channel in channels:
            handler = self.notification_handlers.get(channel)
            if handler:
                try:
                    results[channel] = handler(payload)
                except Exception as e:
                    results[channel] = {"success": False, "error": str(e)}

        return results

    def notify_pipeline_started(self, pipeline_name: str, pipeline_id: str, trigger: str):
        """Notify pipeline started"""
        return self.send_notification(
            event="pipeline_started",
            message=f"Pipeline '{pipeline_name}' ({pipeline_id}) started via {trigger}",
            level="info",
            metadata={"pipeline_id": pipeline_id, "pipeline_name": pipeline_name, "trigger": trigger},
        )

    def notify_pipeline_completed(self, pipeline_name: str, pipeline_id: str, success: bool, duration: float):
        """Notify pipeline completed"""
        level = "success" if success else "error"
        status = "completed successfully" if success else "failed"

        return self.send_notification(
            event="pipeline_completed",
            message=f"Pipeline '{pipeline_name}' ({pipeline_id}) {status} in {duration:.1f}s",
            level=level,
            metadata={
                "pipeline_id": pipeline_id,
                "pipeline_name": pipeline_name,
                "success": success,
                "duration": duration,
            },
        )

    def notify_pipeline_failed(self, pipeline_name: str, pipeline_id: str, task: str, error: str):
        """Notify pipeline failed"""
        return self.send_notification(
            event="pipeline_failed",
            message=f"Pipeline '{pipeline_name}' ({pipeline_id}) failed at task '{task}': {error}",
            level="error",
            metadata={"pipeline_id": pipeline_id, "pipeline_name": pipeline_name, "failed_task": task, "error": error},
        )

    def notify_task_failed(self, pipeline_name: str, pipeline_id: str, task: str, error: str, retry: bool = False):
        """Notify task failed"""
        return self.send_notification(
            event="task_failed",
            message=f"Task '{task}' in pipeline '{pipeline_name}' failed: {error}" + (" (will retry)" if retry else ""),
            level="warning" if retry else "error",
            metadata={
                "pipeline_id": pipeline_id,
                "pipeline_name": pipeline_name,
                "task": task,
                "error": error,
                "retry": retry,
            },
        )

    def notify_approval_required(self, pipeline_name: str, pipeline_id: str, task: str, prompt: str):
        """Notify approval required"""
        return self.send_notification(
            event="approval_required",
            message=f"Approval required for task '{task}' in pipeline '{pipeline_name}': {prompt}",
            level="warning",
            metadata={"pipeline_id": pipeline_id, "pipeline_name": pipeline_name, "task": task},
        )

    def notify_rollback_initiated(self, pipeline_name: str, pipeline_id: str, reason: str):
        """Notify rollback initiated"""
        return self.send_notification(
            event="rollback_initiated",
            message=f"Rollback initiated for pipeline '{pipeline_name}' ({pipeline_id}): {reason}",
            level="warning",
            metadata={"pipeline_id": pipeline_id, "pipeline_name": pipeline_name, "reason": reason},
        )

    # Channel handlers
    def _send_console(self, payload: Dict) -> Dict:
        level = payload["level"].upper()
        print(f"[{level}] {payload['event']}: {payload['message']}")
        return {"success": True}

    def _send_slack(self, payload: Dict) -> Dict:
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not webhook_url:
            return {"success": False, "error": "SLACK_WEBHOOK_URL not configured"}

        color = {"info": "#36a64f", "warning": "#ffcc00", "error": "#ff0000", "success": "#36a64f"}.get(
            payload["level"], "#808080"
        )

        payload_data = {
            "attachments": [
                {
                    "color": color,
                    "title": f"{payload['event']} - {payload['level'].upper()}",
                    "text": payload["message"],
                    "fields": [
                        {"title": k, "value": str(v), "short": True} for k, v in payload.get("metadata", {}).items()
                    ],
                    "ts": int(time.time()),
                }
            ]
        }

        try:
            import requests

            response = requests.post(webhook_url, json=payload_data, timeout=10)
            return {"success": response.status_code == 200}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _send_email(self, payload: Dict) -> Dict:
        # Email implementation would go here
        return {"success": False, "error": "Email not implemented"}

    def _send_webhook(self, payload: Dict) -> Dict:
        webhook_url = os.getenv("WEBHOOK_URL")
        if not webhook_url:
            return {"success": False, "error": "WEBHOOK_URL not configured"}

        try:
            import requests

            response = requests.post(webhook_url, json=payload, timeout=10)
            return {"success": response.status_code == 200}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _send_telegram(self, payload: Dict) -> Dict:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("TELEGRAM_CHAT_ID")
        if not bot_token or not chat_id:
            return {"success": False, "error": "Telegram not configured"}

        try:
            import requests

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            text = f"*{payload['event']}*\n{payload['message']}"
            response = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
            return {"success": response.status_code == 200}
        except Exception as e:
            return {"success": False, "error": str(e)}


class CleanupManager:
    """Manage cleanup of build artifacts, caches, temporary files"""

    def __init__(self, project_path: str = None):
        self.project_path = Path(validate_file_path(project_path, must_exist=True)) if project_path else None
        self.config = get_config()

    def clean_build_artifacts(self, max_age_days: int = 30, dry_run: bool = False) -> Dict[str, Any]:
        """Clean old build artifacts"""
        if not self.project_path:
            return {"success": False, "error": "No project path configured"}

        artifacts_dir = self.project_path / "build" / "outputs"
        if not artifacts_dir.exists():
            return {"success": True, "cleaned": 0, "message": "No artifacts directory"}

        cutoff = time.time() - (max_age_days * 86400)
        cleaned = 0
        freed_bytes = 0
        errors = []

        for artifact in artifacts_dir.rglob("*"):
            if artifact.is_file():
                try:
                    if artifact.stat().st_mtime < cutoff:
                        size = artifact.stat().st_size
                        if not dry_run:
                            artifact.unlink()
                        cleaned += 1
                        freed_bytes += size
                except Exception as e:
                    errors.append(str(e))

        return {
            "success": True,
            "cleaned_files": cleaned,
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "dry_run": dry_run,
            "errors": errors,
        }

    def clean_gradle_caches(self, max_age_days: int = 7, dry_run: bool = False) -> Dict[str, Any]:
        """Clean Gradle caches"""
        if not self.project_path:
            return {"success": False, "error": "No project path configured"}

        gradle_cache = self.project_path / ".gradle"
        if not gradle_cache.exists():
            return {"success": True, "cleaned": 0, "message": "No Gradle cache"}

        cutoff = time.time() - (max_age_days * 86400)
        cleaned = 0
        freed_bytes = 0
        errors = []

        # Clean build cache
        build_cache = gradle_cache / "buildOutputCleanup"
        if build_cache.exists():
            for item in build_cache.rglob("*"):
                if item.is_file():
                    try:
                        if item.stat().st_mtime < cutoff:
                            size = item.stat().st_size
                            if not dry_run:
                                item.unlink()
                            cleaned += 1
                            freed_bytes += size
                    except Exception as e:
                        errors.append(str(e))

        # Clean daemon logs
        daemon_logs = gradle_cache / "daemon"
        if daemon_logs.exists():
            for log in daemon_logs.glob("*.log"):
                try:
                    if log.stat().st_mtime < cutoff:
                        size = log.stat().st_size
                        if not dry_run:
                            log.unlink()
                        cleaned += 1
                        freed_bytes += size
                except Exception as e:
                    errors.append(str(e))

        return {
            "success": True,
            "cleaned_files": cleaned,
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "dry_run": dry_run,
            "errors": errors,
        }

    def clean_temp_files(self, max_age_hours: int = 24, dry_run: bool = False) -> Dict[str, Any]:
        """Clean temporary files"""
        temp_dirs = [Path("/tmp"), Path("/var/tmp"), self.project_path / "build" / "tmp" if self.project_path else None]

        cutoff = time.time() - (max_age_hours * 3600)
        cleaned = 0
        freed_bytes = 0
        errors = []

        for temp_dir in temp_dirs:
            if not temp_dir or not temp_dir.exists():
                continue

            for item in temp_dir.glob("*"):
                try:
                    if item.is_file() and item.stat().st_mtime < cutoff:
                        size = item.stat().st_size
                        if not dry_run:
                            item.unlink()
                        cleaned += 1
                        freed_bytes += size
                    elif item.is_dir() and item.stat().st_mtime < cutoff:
                        # Check if directory is empty or old
                        if not any(item.iterdir()):
                            size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                            if not dry_run:
                                shutil.rmtree(item)
                            cleaned += 1
                            freed_bytes += size
                except Exception as e:
                    errors.append(str(e))

        return {
            "success": True,
            "cleaned_files": cleaned,
            "freed_bytes": freed_bytes,
            "freed_mb": round(freed_bytes / (1024 * 1024), 2),
            "dry_run": dry_run,
            "errors": errors,
        }

    def full_cleanup(self, dry_run: bool = False) -> Dict[str, Any]:
        """Run all cleanup tasks"""
        results = {}

        results["artifacts"] = self.clean_build_artifacts(dry_run=dry_run)
        results["gradle_caches"] = self.clean_gradle_caches(dry_run=dry_run)
        results["temp_files"] = self.clean_temp_files(dry_run=dry_run)

        total_cleaned = sum(r.get("cleaned_files", 0) for r in results.values())
        total_freed = sum(r.get("freed_bytes", 0) for r in results.values())

        return {
            "success": all(r.get("success", False) for r in results.values()),
            "total_cleaned_files": total_cleaned,
            "total_freed_bytes": total_freed,
            "total_freed_mb": round(total_freed / (1024 * 1024), 2),
            "details": results,
        }


class ScheduledTaskManager:
    """Manage scheduled tasks (cron-like)"""

    def __init__(self):
        self.config = get_config()
        self.tasks: Dict[str, Dict] = {}
        self._running = False
        self._thread = None

    def add_task(
        self,
        name: str,
        schedule: str,  # cron expression or "interval:N"
        command: List[str],
        working_dir: str = None,
        env: Dict = None,
        enabled: bool = True,
    ):
        """Add a scheduled task"""
        self.tasks[name] = {
            "name": name,
            "schedule": schedule,
            "command": command,
            "working_dir": working_dir,
            "env": env or {},
            "enabled": enabled,
            "last_run": None,
            "next_run": None,
            "run_count": 0,
            "last_status": None,
        }
        return {"success": True, "task": name}

    def remove_task(self, name: str) -> Dict:
        if name in self.tasks:
            del self.tasks[name]
            return {"success": True}
        return {"success": False, "error": "Task not found"}

    def run_task_now(self, name: str) -> Dict:
        """Run a task immediately"""
        if name not in self.tasks:
            return {"success": False, "error": "Task not found"}

        task = self.tasks[name]
        return self._execute_task(task)

    def _execute_task(self, task: Dict) -> Dict:
        try:
            cwd = (
                validate_file_path(task["working_dir"], must_exist=True, allow_outside_workspace=True)
                if task["working_dir"]
                else None
            )
            env = {**os.environ, **task["env"]}

            result = safe_run(task["command"], cwd=str(cwd) if cwd else None, timeout=3600, env=env)

            task["last_run"] = datetime.now().isoformat()
            task["run_count"] += 1
            task["last_status"] = "success" if result.returncode == 0 else "failed"

            return {"success": result.returncode == 0, "output": result.stdout, "error": result.stderr}
        except Exception as e:
            task["last_run"] = datetime.now().isoformat()
            task["last_status"] = "error"
            return {"success": False, "error": str(e)}

    def get_task_status(self, name: str) -> Optional[Dict]:
        return self.tasks.get(name)

    def list_tasks(self) -> List[Dict]:
        return [{"name": k, **v} for k, v in self.tasks.items()]


# Standalone functions for MCP tool integration
def create_rollback_plan(pipeline_id: str, project_path: str, failed_task: str, error: str) -> Dict[str, Any]:
    """MCP tool: Create rollback plan"""
    try:
        manager = RollbackManager(project_path)
        plan = manager.create_rollback_plan(pipeline_id, failed_task, error)
        return {"success": True, "plan": asdict(plan)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def execute_rollback(project_path: str, pipeline_id: str) -> Dict[str, Any]:
    """MCP tool: Execute rollback plan"""
    try:
        manager = RollbackManager(project_path)
        plan_data = manager.memory.get_persistent_record(f"rollback_plan_{pipeline_id}", category="rollbacks")
        if not plan_data:
            return {"success": False, "error": "No rollback plan found"}

        plan = RollbackPlan(**plan_data)
        return manager.execute_rollback(plan)
    except Exception as e:
        return {"success": False, "error": str(e)}


def send_notification(
    event: str, message: str, level: str = "info", channels: List[str] = None, metadata: Dict = None
) -> Dict[str, Any]:
    """MCP tool: Send notification"""
    try:
        notifier = NotificationManager()
        return notifier.send_notification(event, message, level, channels, metadata)
    except Exception as e:
        return {"success": False, "error": str(e)}


def cleanup_artifacts(project_path: str, max_age_days: int = 30, dry_run: bool = False) -> Dict[str, Any]:
    """MCP tool: Clean build artifacts"""
    try:
        manager = CleanupManager(project_path)
        return manager.clean_build_artifacts(max_age_days, dry_run)
    except Exception as e:
        return {"success": False, "error": str(e)}


def cleanup_gradle_caches(project_path: str, max_age_days: int = 7, dry_run: bool = False) -> Dict[str, Any]:
    """MCP tool: Clean Gradle caches"""
    try:
        manager = CleanupManager(project_path)
        return manager.clean_gradle_caches(max_age_days, dry_run)
    except Exception as e:
        return {"success": False, "error": str(e)}


def cleanup_temp_files(project_path: str = None, max_age_hours: int = 24, dry_run: bool = False) -> Dict[str, Any]:
    """MCP tool: Clean temporary files"""
    try:
        manager = CleanupManager(project_path)
        return manager.clean_temp_files(max_age_hours, dry_run)
    except Exception as e:
        return {"success": False, "error": str(e)}


def full_cleanup(project_path: str, dry_run: bool = False) -> Dict[str, Any]:
    """MCP tool: Run full cleanup"""
    try:
        manager = CleanupManager(project_path)
        return manager.full_cleanup(dry_run)
    except Exception as e:
        return {"success": False, "error": str(e)}


def schedule_task(
    name: str, schedule: str, command: List[str], working_dir: str = None, env: Dict = None, enabled: bool = True
) -> Dict[str, Any]:
    """MCP tool: Schedule a task"""
    try:
        manager = ScheduledTaskManager()
        return manager.add_task(name, schedule, command, working_dir, env, enabled)
    except Exception as e:
        return {"success": False, "error": str(e)}


def run_scheduled_task(name: str) -> Dict[str, Any]:
    """MCP tool: Run scheduled task now"""
    try:
        manager = ScheduledTaskManager()
        return manager.run_task_now(name)
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python automation.py <command> [args]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "cleanup":
        project = sys.argv[2] if len(sys.argv) > 2 else "."
        dry_run = "--dry-run" in sys.argv
        manager = CleanupManager(project)
        result = manager.full_cleanup(dry_run)
        print(json.dumps(result, indent=2))
    elif cmd == "notify":
        event = sys.argv[2]
        message = sys.argv[3]
        notifier = NotificationManager()
        result = notifier.send_notification(event, message)
        print(json.dumps(result, indent=2))
    else:
        print(f"Unknown command: {cmd}")
