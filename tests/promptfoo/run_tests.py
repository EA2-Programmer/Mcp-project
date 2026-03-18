#!/usr/bin/env python3
"""
Professional test runner for TrakSYS MCP evaluation.
"""
import subprocess
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestRunner:
    def __init__(self):
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.results_dir = Path("reports")
        self.results_dir.mkdir(exist_ok=True)

    def verify_mcpo_running(self) -> bool:
        """Check if mcpo endpoint is accessible by calling a simple tool."""
        import requests
        try:
            # Try to call get_tool_explanation (doesn't need DB)
            response = requests.post(
                "http://localhost:8000/get_tool_explanation",
                json={"params": {"tool_name": "get_batches"}},
                headers={
                    "Authorization": f"Bearer {os.getenv('WEBUI_SECRET_KEY', 'cQDOOOKH1QRqYqRt')}",
                    "Content-Type": "application/json"
                },
                timeout=5
            )
            return response.status_code == 200
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def find_promptfoo(self):
        """Find promptfoo executable in common locations."""
        possible_paths = [
            "promptfoo",
            "promptfoo.cmd",
            r"C:\Users\edobo\AppData\Roaming\npm\promptfoo.cmd",
            r"C:\Program Files\nodejs\promptfoo.cmd",
        ]

        for path in possible_paths:
            try:
                # Check if command exists
                result = subprocess.run(
                    [path, "--version"],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                if result.returncode == 0:
                    print(f"✅ Found promptfoo at: {path}")
                    return path
            except (subprocess.SubprocessError, FileNotFoundError):
                continue

        return None

    def run_promptfoo(self):
        """Execute promptfoo evaluation."""
        promptfoo_cmd = self.find_promptfoo()

        if not promptfoo_cmd:
            print("❌ Could not find promptfoo executable. Please install: npm install -g promptfoo")
            return False

        # Use the correct config file
        config_file = "promptfooconfig.yaml"

        cmd = [
            promptfoo_cmd, "eval",
            "-c", config_file,
            "--output", str(self.results_dir / f"results_{self.timestamp}.json"),
            "--table",
            "--share"
        ]

        print(f"🚀 Running: {' '.join(cmd)}")

        # IMPORTANT: Add encoding='utf-8' and errors='replace' to handle Unicode
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )

        if result.returncode != 0:
            print(f"❌ promptfoo failed: {result.stderr}")
            return False

        print("✅ promptfoo completed")
        return True

    def generate_report(self):
        """Generate human-readable report."""
        results_file = self.results_dir / f"results_{self.timestamp}.json"

        if not results_file.exists():
            print(f"❌ Results file not found: {results_file}")
            return

        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)

        # Calculate metrics
        total = len(results.get('results', []))
        passed = sum(1 for r in results.get('results', []) if r.get('success', False))
        failed = total - passed

        # Category breakdown
        categories = {}
        for r in results.get('results', []):
            test = r.get('test', {}).get('vars', {})
            cat = test.get('category', 'unknown')
            if cat not in categories:
                categories[cat] = {'total': 0, 'passed': 0}
            categories[cat]['total'] += 1
            if r.get('success'):
                categories[cat]['passed'] += 1

        # Print report
        print("\n" + "=" * 60)
        print("📊 TRAKSYS MCP TEST REPORT")
        print("=" * 60)
        print(f"Timestamp: {self.timestamp}")
        print(f"Total Tests: {total}")
        print(f"Passed: {passed} ({passed / total * 100:.1f}%)")
        print(f"Failed: {failed} ({failed / total * 100:.1f}%)")
        print("\n📈 Category Breakdown:")
        for cat, stats in categories.items():
            rate = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f"  {cat:<12}: {stats['passed']:2}/{stats['total']:2} ({rate:5.1f}%)")

        # Save report
        report_file = self.results_dir / f"report_{self.timestamp}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(f"TrakSYS MCP Test Report - {self.timestamp}\n")
            f.write(f"Pass Rate: {passed / total * 100:.1f}% ({passed}/{total})\n\n")
            for cat, stats in categories.items():
                f.write(f"{cat}: {stats['passed']}/{stats['total']}\n")

        print(f"\n📄 Report saved: {report_file}")

        # Check if shareable link was created
        if 'shareableUrl' in results and results['shareableUrl']:
            print(f"🔗 Shareable results: {results['shareableUrl']}")

    def run(self):
        """Execute full test pipeline."""
        print("🔍 Verifying mcpo endpoint...")
        if not self.verify_mcpo_running():
            print("❌ mcpo endpoint not accessible at http://localhost:8000")
            print("   Make sure your Docker containers are running:")
            print("   docker-compose ps")
            return 1

        print("✅ mcpo endpoint verified")

        if not self.run_promptfoo():
            return 1

        self.generate_report()
        return 0


if __name__ == "__main__":
    runner = TestRunner()
    sys.exit(runner.run())