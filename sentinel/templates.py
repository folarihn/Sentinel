"""Seven mission templates expressed entirely as enforceable policy fields."""

from copy import deepcopy

TEMPLATES = {
    "safe-coding": {
        "name": "Safe Coding",
        "description": "Project-local development; sensitive Git and deployment actions still require native approval.",
        "approved_tools": [
            "terminal",
            "read_file",
            "write_file",
            "search_files",
            "patch",
        ],
        "allowed_domains": [],
        "allow_deployment": False,
    },
    "repository-maintenance": {
        "name": "Repository Maintenance",
        "description": "Inspect and maintain a local repository; destructive Git remains blocked.",
        "approved_tools": [
            "terminal",
            "read_file",
            "write_file",
            "search_files",
            "patch",
        ],
        "allowed_domains": ["github.com"],
        "allow_deployment": False,
    },
    "research": {
        "name": "Research",
        "description": "Read-only local research; explicitly choose permitted network domains.",
        "approved_tools": ["read_file", "search_files", "web_search", "web_extract"],
        "restricted_tools": ["terminal", "write_file", "patch"],
        "allowed_domains": [],
        "allow_deployment": False,
    },
    "deployment-investigation": {
        "name": "Deployment Investigation",
        "description": "Inspect local deployment evidence; deployment execution is outside mission authority.",
        "approved_tools": ["terminal", "read_file", "search_files"],
        "restricted_tools": ["write_file", "patch"],
        "allowed_domains": [],
        "allow_deployment": False,
    },
    "local-file-organization": {
        "name": "Local File Organization",
        "description": "Read and write only the chosen workspace; no terminal or network tools.",
        "approved_tools": ["read_file", "write_file", "search_files", "patch"],
        "restricted_tools": ["terminal", "web_search", "web_extract"],
        "allowed_domains": [],
        "allow_deployment": False,
    },
    "experimental-agent": {
        "name": "Experimental Agent",
        "description": "Disposable local experimentation with mandatory protections and no network destinations.",
        "approved_tools": [
            "terminal",
            "read_file",
            "write_file",
            "search_files",
            "patch",
        ],
        "allowed_domains": [],
        "allow_deployment": False,
    },
    "restricted-automation": {
        "name": "Restricted Automation",
        "description": "Read-only automated inspection; expand tool grants deliberately.",
        "approved_tools": ["read_file", "search_files"],
        "restricted_tools": [
            "terminal",
            "write_file",
            "patch",
            "web_search",
            "web_extract",
        ],
        "allowed_domains": [],
        "allow_deployment": False,
    },
}


def mission_template(key, workspace, session_id=""):
    if key not in TEMPLATES:
        raise ValueError("Unknown mission template")
    return {
        **deepcopy(TEMPLATES[key]),
        "template": key,
        "status": "DRAFT",
        "session_id": session_id,
        "allowed_directories": [str(workspace)],
        "restricted_directories": [],
        "required_approvals": [],
    }
