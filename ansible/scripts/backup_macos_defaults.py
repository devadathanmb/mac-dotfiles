#!/usr/bin/env python3
"""Create a timestamped backup of the macOS defaults managed by this repo."""

from __future__ import annotations

import argparse
import datetime as dt
import platform
import subprocess
from pathlib import Path
from typing import Any

import yaml


def managed_defaults(source_dir: Path) -> list[dict[str, Any]]:
    defaults: list[dict[str, Any]] = []

    for task_file in sorted(source_dir.glob("*.yml")):
        tasks = yaml.safe_load(task_file.read_text()) or []
        for task in tasks:
            if not isinstance(task, dict):
                continue

            osx_default = task.get("community.general.osx_defaults")
            if not isinstance(osx_default, dict):
                continue

            entry = {
                "name": task.get("name"),
                "domain": osx_default["domain"],
                "key": osx_default["key"],
                "type": osx_default["type"],
                "state": "present",
            }

            if "host" in osx_default:
                entry["host"] = osx_default["host"]

            if task.get("become") is True:
                entry["become"] = True

            defaults.append(entry)

    return defaults


def read_default(entry: dict[str, Any]) -> tuple[bool, str]:
    command = ["defaults"]
    if entry.get("host") == "currentHost":
        command.append("-currentHost")

    command.extend(["read", str(entry["domain"]), str(entry["key"])])
    result = subprocess.run(command, capture_output=True, text=True, check=False)

    if result.returncode != 0:
        return False, result.stderr.strip()

    return True, result.stdout.strip()


def read_type(entry: dict[str, Any]) -> str:
    command = ["defaults"]
    if entry.get("host") == "currentHost":
        command.append("-currentHost")

    command.extend(["read-type", str(entry["domain"]), str(entry["key"])])
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return str(entry["type"])

    raw_type = result.stdout.strip().removeprefix("Type is ")
    return {
        "boolean": "bool",
        "integer": "int",
        "float": "float",
        "string": "string",
        "array": "array",
    }.get(raw_type, str(entry["type"]))


def parse_value(raw_value: str, value_type: str) -> Any:
    if value_type == "bool":
        return raw_value.lower() in {"1", "true", "yes"}

    if value_type == "int":
        return int(raw_value)

    if value_type == "float":
        return float(raw_value)

    if value_type == "array":
        lines = [line.strip().rstrip(",") for line in raw_value.splitlines()]
        values = [line for line in lines if line and line not in {"(", ")"}]
        return [parse_array_item(value) for value in values]

    return raw_value


def parse_array_item(value: str) -> Any:
    value = value.strip().strip('"')
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def backup_defaults(source_dir: Path) -> list[dict[str, Any]]:
    backed_up: list[dict[str, Any]] = []

    for entry in managed_defaults(source_dir):
        exists, raw_value = read_default(entry)
        backed_up_entry = dict(entry)

        if exists:
            actual_type = read_type(entry)
            backed_up_entry["type"] = actual_type
            backed_up_entry["state"] = "present"
            backed_up_entry["value"] = parse_value(raw_value, actual_type)
        else:
            backed_up_entry["state"] = "absent"
            backed_up_entry.pop("value", None)

        backed_up.append(backed_up_entry)

    return backed_up


def write_backup(output_dir: Path, defaults: list[dict[str, Any]]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    output_file = output_dir / f"macos-defaults-{timestamp}.yml"
    content = yaml.safe_dump(
        {"macos_defaults": defaults},
        default_flow_style=False,
        sort_keys=False,
        width=120,
    )
    output_file.write_text("---\n" + content)
    return output_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    if platform.system() != "Darwin":
        raise SystemExit("macOS defaults backup can only run on macOS.")

    defaults = backup_defaults(args.source_dir)
    output_file = write_backup(args.output_dir, defaults)
    present_count = sum(1 for item in defaults if item.get("state") == "present")
    absent_count = sum(1 for item in defaults if item.get("state") == "absent")

    print(f"Backed up {present_count} present and {absent_count} absent macOS defaults to {output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
