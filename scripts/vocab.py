#!/usr/bin/env python3
"""Print the CyberAgents Exchange controlled vocabularies from the live validator.py.

Usage: python3 vocab.py <exchange_clone_dir>
Prints JSON: {field: [allowed values]} - always read values from here, never from memory.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import validate_listing as vl  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    ex = Path(sys.argv[1]).resolve()
    if not (ex / "validator.py").is_file():
        print(f"{ex} is not a clone of tenable/cyberagents-exchange (no validator.py)", file=sys.stderr)
        return 2
    vl.install_shims()
    v = vl.load_validator(ex)
    lit = v._extract_literals_from_field
    out = {
        "tier": lit(v.Entry, "tier"),
        "integrations": lit(v.Entry, "integrations"),
        "domains (closed - never extend)": lit(v.Entry, "domains"),
        "skill.compatible_platforms": lit(v.Skill, "compatible_platforms"),
        "mcp.compatible_clients": lit(v.MCPServer, "compatible_clients"),
        "mcp.transport": lit(v.MCPServer, "transport"),
        "mcp.auth_method": lit(v.MCPServer, "auth_method"),
        "mcp.runtime": lit(v.MCPServer, "runtime"),
        "playbook.agents_used.type": v._literal_strings(v.PlaybookAgent.model_fields["type"].annotation),
        "playbook_type": sorted(set().union(*(lit(m, "playbook_type") for m in (v.StandardPlaybook, v.SponsoredPlaybook, v.N8nPlaybook)))),
    }
    print(json.dumps({k: sorted(val) for k, val in out.items()}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
